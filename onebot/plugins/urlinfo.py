# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.urlinfo` Urlinfo plugin
================================================

This plugin shows information about urls posted.


"""

from contextlib import closing
import logging
import os
import re
import pickle
import ipaddress
import socket
import time
import datetime
from io import StringIO
from typing import Callable, List, Optional, Self, Tuple
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
import requests
import requests.exceptions
from irc3 import plugin, event
from isodate import parse_duration

import prawcore
import praw
import praw.models
import praw.exceptions

YOUTUBE_URLS = [
    "www.youtube.com",
    "youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
]


def sizeof_fmt(num, suffix="B"):
    """Format printable versions for bytes"""
    if num == -1:
        return "large"
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


def timedelta_format(duration: datetime.timedelta):
    seconds = int(duration.total_seconds())
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return "%dd%dh%dm%ds" % (days, hours, minutes, seconds)
    elif hours > 0:
        return "%dh%dm%ds" % (hours, minutes, seconds)
    else:
        return "%dm%ds" % (minutes, seconds)


def _read_body(response) -> Tuple[int, Optional[str]]:
    """Count the size of the body of files"""
    content = StringIO()
    size = 0
    start_time = time.time()
    for chunk in response.iter_content(102400):
        if size < 5 * 1048576:
            content.write(chunk.decode("utf-8", "ignore"))
        elif size > 30 * 1048576:
            response.close()
            return -1, None
        if time.time() - start_time > 10:
            response.close()
            return -1, None
        size += len(chunk)

    return size, content.getvalue()


URL_PATTERN = re.compile(r"\bhttps?://\S+")


def _find_urls(string) -> List[str]:
    """Find all urls in a string"""
    urls = []
    for match in URL_PATTERN.finditer(string):
        url = match.group(0).rstrip(".,'\"")
        # Find matching pairs, strip others
        for lbr, rbr in [("(", ")"), ("[", "]"), ("{", "}"), ("<", ">")]:
            rest = url
            count = 0
            # FIXME this is still really hacky
            for char in reversed(url):
                # ends with rb
                if char == rbr:
                    # find lbr and what follows
                    split = rest.split(lbr, maxsplit=1)
                    if len(split) < 2:
                        count += 1
                    else:
                        rest = split[1]
                        if rbr in rest.rstrip(rbr):
                            count += 1
                else:
                    break
            if count > 0:
                url = url[:-count]
        urls.append(url)
    return urls


class UrlSkipException(Exception):
    pass


class UrlRedirectException(Exception):
    def __init__(self, next: str):
        super().__init__()
        self.next = next


REDDIT_USER_PATTERN = re.compile(r"^/u(?:ser)?/(?P<user>[^/]+)/?$")

# User agent for PRAW
USER_AGENT_STRING = "OneBot by /u/DutchDudeWCD"


@plugin
class UrlInfo(object):
    """Bot User Interface plugin

    Configuration settings:
        - ``cookiejar``: Cookies to identify to sites with
        - ``ignored_classes``: ignored MIME classes
        - ``ignored_apps``: ignored ``application/`` classes
        - ``ignored_channels``: channels to not post information in
        - ``ignored_nicks``: whom to ignore
        - ``youtube_api_key``: key for the YouTube API

    **URL Map**

    Using the section ``[onebot.plugins.urlinfo.urlmap]`` it's possible
    to automatically translate urls. Set them as from=to. It's a dumb
    find-and-replace.
    """

    def __init__(self, bot):
        """Init"""
        self.bot = bot
        self.config = bot.config.get(__name__, {})
        self.log: logging.Logger = self.bot.log.getChild(__name__)
        cookiejar_file = self.config.get("cookiejar")
        self.ignored_classes: list[str] = self.config.get(
            "ignored_classes", ["image", "text"]
        )
        self.ignored_apps: list[str] = self.config.get("ignored_apps", ["pdf"])
        self.ignored_channels: list[str] = self.config.get("ignored_channels", [])
        self.ignored_nicks: list[str] = self.config.get("ignored_nicks", [])
        self.youtube_api_key: Optional[str] = self.config.get("youtube_api_key")
        reddit_client_id: Optional[str] = self.config.get("reddit_client_id")
        reddit_client_secret: Optional[str] = self.config.get("reddit_client_secret")
        self.cookiejar = None
        if cookiejar_file:
            with open(cookiejar_file, "rb") as f:
                self.cookiejar = pickle.load(f)

        self.urlmap = self.bot.config.get(__name__ + ".urlmap", {})

        self.praw = None
        if "praw_client_id" in os.environ and "praw_client_secret" in os.environ:
            self.praw = praw.Reddit(user_agent=USER_AGENT_STRING)
        if reddit_client_id is not None and reddit_client_secret is not None:
            self.praw = praw.Reddit(
                client_id=reddit_client_id,
                client_secret=reddit_client_secret,
                user_agent=USER_AGENT_STRING,
            )

        # URL processors
        self.url_processors: List[Callable[..., Optional[list[str]]]] = [
            self._process_url_local,
            self._process_url_urlmap,
            self._process_url_twitter,
            self._process_url_reddit,
            self._process_url_youtube,
            self._process_url_default,
        ]

    def _process_url(
        self, session: requests.Session, url: str, **kwargs
    ) -> Optional[list[str]]:
        i = 0
        redirects = 0
        while i < len(self.url_processors):
            function = self.url_processors[i]
            i += 1
            try:
                self.log.debug("Processing %s via %s", url, function.__name__)
                result = function(session, url, **kwargs)
                if result is not None:
                    return result
            except UrlRedirectException as e:
                if redirects > 10:
                    return ["Too many redirects."]
                url = e.next
                redirects += 1
                i = 0
            except UrlSkipException:
                return None

        return None

    def _process_url_local(self, _session, url: str, **kwargs):
        try:
            # filter out private addresses
            # May raise exceptions
            for _f, _t, _p, _c, sockaddr in socket.getaddrinfo(
                urlparse(url).hostname, None
            ):
                ip = ipaddress.ip_address(sockaddr[0])
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                ):
                    raise UrlSkipException()
        except Exception:
            raise UrlSkipException()

    def _process_url_urlmap(self, session, url: str, **kwargs) -> None:
        o = urlparse(url)
        assert o.hostname is not None
        if o.hostname in self.urlmap:
            url = url.replace(o.hostname, self.urlmap[o.hostname], 1)
            raise UrlRedirectException(url)

    def _process_url_reddit(self, session: requests.Session, url: str, **kwargs):
        """Get reddit information through the api."""
        urlinfo = urlparse(url)
        assert urlinfo.hostname is not None
        if not (
            urlinfo.hostname == "reddit.com" or urlinfo.hostname.endswith(".reddit.com")
        ):
            return
        if self.praw is None:
            return ["Reddit support is not enabled, API key not provided."]

        try:
            if match := REDDIT_USER_PATTERN.match(urlinfo.path):
                return [f"/u/{match.group(1)} on Reddit"]

            try:
                # Separately parse so that we prevent the not-found error
                comment_id = praw.models.Comment.id_from_url(url)
                comment = self.praw.comment(comment_id)
                return [
                    f"/{comment.submission.subreddit.display_name_prefixed}",
                    "comment by",
                    comment.author.name,
                    "on",
                    f"“{comment.submission.title}”",
                ]
            except prawcore.exceptions.NotFound:
                return ["Comment not found"]
            except praw.exceptions.PRAWException:
                pass

            try:
                # Separately parse so that we prevent the not-found error
                submission_id = praw.models.Submission.id_from_url(url)
                submission = self.praw.submission(submission_id)
                return [
                    f"/{submission.subreddit.display_name_prefixed}:",
                    f"“{submission.title}”",
                    "by",
                    f"/u/{submission.author}",
                ]
            except prawcore.exceptions.NotFound:
                return ["Subreddit not found"]
            except praw.exceptions.InvalidURL:
                pass

            return ["Reddit."]

        except praw.exceptions.PRAWException as e:
            self.log.exception("Reddit error")
            return ["Some exception occurred", str(e)]
        except prawcore.exceptions.PrawcoreException as e:
            self.log.exception("Reddit error")
            return ["Some exception occurred", str(e)]

    def _process_url_twitter(self, session: requests.Session, url, **kwargs):
        """Skip twitter urls because they're no longer useful"""
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        if (
            hostname == "twitter.com"
            or hostname.endswith(".twitter.com")
            or hostname == "x.com"
        ):
            return ["Twitter (or as Elon would insist, X)"]

    def _process_url_youtube(self, session, url, **kwargs):
        """YouTube URLs don't contain a <title>"""
        self.log.debug("Checking if this is a YouTube URL")
        parsed_host = urlparse(url)
        if parsed_host.hostname == "youtu.be" or parsed_host.path.startswith(
            "/shorts/"
        ):
            self.log.debug("Short YouTube URL")
            video_id = parsed_host.path.lstrip("/")
        elif parsed_host.hostname in YOUTUBE_URLS:
            args = parse_qs(parsed_host.query)
            self.log.debug("Parsed args: '%r'", args)
            video_id = args.get("v", [])[0]
            if not video_id:
                return
        else:
            return
        url = "https://www.googleapis.com/youtube/v3/videos"
        self.log.debug("Video ID = '%s'", video_id)
        params = {
            "id": video_id,
            "hl": "en",
            "key": self.youtube_api_key,
            "part": ["snippet", "contentDetails"],
        }
        with closing(session.get(url, params=params, timeout=4)) as response:
            try:
                data = response.json()
                self.log.debug("Response: %r", data)
                if response.status_code != 200:
                    return [f"Got response code {response.status_code}"]
            except ValueError:
                return ["Invalid JSON response from YouTube API"]
            title = data["items"][0]["snippet"]["title"]
            duration = timedelta_format(
                parse_duration(data["items"][0]["contentDetails"]["duration"])
            )
            return [f"“{title}” ({duration})"]

    def _process_url_default(self, session: requests.Session, url: str, **kwargs):
        """Process an URL"""
        message = []
        try:
            with closing(
                session.get(url, allow_redirects=False, timeout=4, stream=True)
            ) as response:
                if response.status_code in (301, 302):
                    if response.next is not None and response.next.url is not None:
                        raise UrlRedirectException(response.next.url)
                content_type = response.headers.get("Content-Type", "text/html").split(
                    ";"
                )[0]
                size = int(response.headers.get("Content-Length", 0))

                # handle chunked transfers
                content = None
                if size == 0:
                    size, content = _read_body(response)

                self.log.debug("File size: {}".format(repr(size)))
                if not response.ok:
                    message.append(f"error: HTTP {response.status_code}")
                    message.append(response.reason.lower())
                elif size < 0:
                    message.append("Safety error: unknown size, not reading")
                elif content_type not in ("text/html", "application/xhtml+xml"):
                    class_, app = content_type.split("/")
                    if not (
                        (class_ in self.ignored_classes or app in self.ignored_apps)
                        and size < (1048576 * 5)
                    ):
                        message.append("Content-Type:")
                        message.append(content_type)
                        message.append("Filesize:")
                        message.append(sizeof_fmt(size))
                elif size < (1048576 * 2):
                    soup = BeautifulSoup(
                        (content or response.content.decode("utf-8", "ignore")),
                        "html5lib",
                    )
                    if soup.title is not None and soup.title.string is not None:
                        title = soup.title.string.strip()
                        if len(title) > 320:
                            title = "{}…".format(title[:310])
                        message.append("“{}”".format(title))
            # endwith
        except requests.exceptions.Timeout:
            self.log.debug("Error while requesting %s", url)
            message.append("Timeout")
        return message

    @event(
        r"^:(?P<mask>\S+!\S+@\S+) (?P<event>(PRIVMSG|NOTICE)) "
        r"(?P<target>\S+) :\s*(?P<data>(.*(https?://)).*)$"
    )
    def on_message(self, mask, event, target, data):
        if (
            mask.nick == self.bot.nick
            or event == "NOTICE"
            or not target.is_channel
            or target in self.ignored_channels
            or mask.nick in self.ignored_nicks
        ):
            return
        index = 1
        messages: List[str] = []
        urls = _find_urls(data)
        for url in urls:
            message: list[str] = []
            if len(urls) > 1:
                message.append("({})".format(index))
                index += 1
            with requests.Session() as session:
                session.headers.update(
                    {
                        "User-Agent": "script:onebot:irc",
                        "Accept-Language": "en-GB, en-US, en, nl-NL, nl",
                    }
                )
                if self.cookiejar:
                    session.cookies = self.cookiejar
                self.log.debug("processing %s", url)
                try:
                    urlmesg = self._process_url(session, url)
                    if not urlmesg:
                        continue
                    else:
                        message.extend(urlmesg)
                except Exception:
                    self.log.exception("Exception while requesting %s", url)
                    continue
                # end try
            # end with session
            if message:
                messages.append(" ".join(message))
        if messages:
            self.bot.privmsg(target, "{}.".format(" ".join(messages)))

    @classmethod
    def reload(cls, old: Self) -> Self:  # pragma: no cover
        return cls(old.bot)
