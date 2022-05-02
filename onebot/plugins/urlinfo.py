# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.urlinfo` Urlinfo plugin
================================================

This plugin shows information about urls posted.


"""

from contextlib import closing
import re
import pickle
import ipaddress
import socket
import time
import datetime
from io import StringIO
from typing import List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
import requests
import requests.exceptions
from irc3 import plugin, event
from isodate import parse_duration

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


REDDIT_THREAD_PATTERN = re.compile(
    r"^/r/(?P<subreddit>[^/]+)/comments/(?P<thread>[^/]+)(?:/[^/]+/?)?$"
)
REDDIT_COMMENT_PATTERN = re.compile(
    r"^/r/(?P<subreddit>[^/]+)/comments/(?P<thread>[^/]+)/[^/]+/(?P<comment>\w+)/?$"
)
REDDIT_USER_PATTERN = re.compile(r"^/u(?:ser)?/(?P<user>[^/]+)/?$")


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
        - ``twitter_bearer_token``: Twitter API key

    **URL Map**

    Using the section ``[onebot.plugins.urlinfo.urlmap]`` it's possible
    to automatically translate urls. Set them as from=to. It's a dumb
    find-and-replace.
    """

    def __init__(self, bot):
        """Init"""
        self.bot = bot
        self.config = bot.config.get(__name__, {})
        self.log = self.bot.log.getChild(__name__)
        cookiejar_file = self.config.get("cookiejar")
        self.ignored_classes = self.config.get("ignored_classes", ["image", "text"])
        self.ignored_apps = self.config.get("ignored_apps", ["pdf"])
        self.ignored_channels = self.config.get("ignored_channels", [])
        self.ignored_nicks = self.config.get("ignored_nicks", [])
        self.youtube_api_key = self.config.get("youtube_api_key", None)
        self.twitter_bearer_token = self.config.get("twitter_bearer_token", None)
        self.cookiejar = None
        if cookiejar_file:
            with open(cookiejar_file, "rb") as f:
                self.cookiejar = pickle.load(f)

        self.urlmap = self.bot.config.get(__name__ + ".urlmap", {})

        # URL processors
        self.url_processors = [
            self._process_url_local,
            self._process_url_urlmap,
            self._process_url_twitter,
            self._process_url_reddit,
            self._process_url_youtube,
            self._process_url_default,
        ]

    def _process_url(self, session, url, **kwargs) -> Optional[List[str]]:
        i = 0
        redirects = 0
        while i < len(self.url_processors):
            function = self.url_processors[i]
            i += 1
            try:
                self.log.debug("Processing %s via %s", url, function.__name__)
                result = function(session, url, **kwargs)
            except UrlRedirectException as e:
                if redirects > 10:
                    return ["Too many redirects."]
                url = e.next
                redirects += 1
                i = 0
            except UrlSkipException:
                return None
            if result:
                return result

        return None

    def _process_url_local(self, _session, url, **kwargs):
        try:
            # filter out private addresses
            # May raise exceptions
            for (_f, _t, _p, _c, sockaddr) in socket.getaddrinfo(
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

    def _process_url_urlmap(self, session, url, already_extended=False):
        # FIXME what does this even do
        if already_extended:
            return
        o = urlparse(url)
        if o.hostname in self.urlmap:
            url = url.replace(o.hostname, self.urlmap[o.hostname], 1)
            raise UrlRedirectException(url)

    def _process_url_reddit(self, session, url, **kwargs):
        """Get reddit information through the api.

        Partially based on https://github.com/butterscotchstallion/limnoria-plugins/blob/master/SpiffyTitles/plugin.py#L960
        """
        urlinfo = urlparse(url)
        if not (
            urlinfo.hostname == "reddit.com" or urlinfo.hostname.endswith(".reddit.com")
        ):
            return

        # Thread information
        if match := REDDIT_THREAD_PATTERN.match(urlinfo.path):
            apiurl = f"https://reddit.com/r/{match.group('subreddit')}/comments/{match.group('thread')}.json"

            def formatter(response):
                data = response[0]["data"]["children"][0]["data"]
                return [f"/r/{match.group('subreddit')}:", data.get("title")]

        elif match := REDDIT_COMMENT_PATTERN.match(urlinfo.path):
            apiurl = f"https://reddit.com/r/{match.group('subreddit')}/comments/{match.group('thread')}/x/{match.group('comment')}.json"

            def formatter(response):
                data = response[1]["data"]["children"][0]["data"]
                title = response[0]["data"]["children"][0]["data"]["title"]
                return [
                    f"/r/{match.group('subreddit')} comment by {data.get('author')} on “{title}”"
                ]

        elif match := REDDIT_USER_PATTERN.match(urlinfo.path):
            apiurl = f"https://reddit.com/user/{match.group('user')}/about.json"

            def formatter(response):
                data = response["data"]
                return [f"/u/{data['name']} on Reddit"]

        else:
            self.log.warning("Unsupported reddit url: '%s'", urlinfo.path)
            return ["Reddit"]

        with closing(session.get(apiurl, timeout=4)) as response:
            try:
                attempts = 0
                while attempts < 3:
                    attempts += 1
                    data = response.json()
                    self.log.debug("Response: %r", data)
                    if response.status_code == 429:
                        time.sleep(0.5 * attempts)
                        self.log.debug("Retrying reddit request")
                        continue
                    elif response.status_code != 200:
                        return [f"Got response code {response.status_code}"]
                return formatter(data)

            except ValueError:
                return ["Invalid JSON response from Reddit API"]

    def _process_url_twitter(self, session: requests.Session, url, **kwargs):
        """Skip twitter urls because they're no longer useful"""
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        tweet_regex = re.compile(
            r"^/(?P<username>[A-Za-z0-9_]{1,15})/status/(?P<id>\d+)"
        )
        if hostname == "twitter.com" or hostname == "mobile.twitter.com":
            if self.twitter_bearer_token is None:
                raise UrlSkipException()

            potential_username = parsed_url.path[1:].split("/", 1)[0]

            # Get tweet
            if matches := tweet_regex.search(parsed_url.path):
                id = matches.group("id")
                username = matches.group("username")
                self.log.debug("Twitter url for tweet %d", id)
                with closing(
                    session.get(
                        "https://api.twitter.com/2/tweets?"
                        "expansions=author_id,in_reply_to_user_id&"
                        "user.fields=name,verified&"
                        "tweet.fields=author_id&"
                        f"ids={id}",
                        headers={
                            "Authorization": f"Bearer {self.twitter_bearer_token}"
                        },
                    )
                ) as response:
                    data = response.json()
                    if "data" not in data:
                        return ["Tweet not found."]
                    tweet = data["data"][0]
                    author_id = tweet["author_id"]
                    replying_to = None
                    for user in data["includes"]["users"]:
                        if user["id"] == author_id:
                            author = user
                        if user["id"] == tweet.get("in_reply_to_user_id"):
                            replying_to = user
                    verified = ""

                    # Don't allow OneBot to be an id oracle
                    if author["username"].lower() != username.lower():
                        return ["Tweet not found"]

                    if author["verified"]:
                        verified = " ✅"
                    message = [
                        author["name"],
                        f"(@{author['username']}{verified}):",
                    ]
                    if replying_to is not None:
                        message.append(f"@{replying_to['name']}")
                    message.append(data["data"][0]["text"].replace("\n", " "))
                    return message

            if potential_username != "":
                if potential_username in (
                    "i",
                    "login",
                    "home",
                    "context",
                    "notifications",
                    "messages",
                    "compose",
                    "settings",
                ):
                    return ["Twitter"]
                with closing(
                    session.get(
                        f"https://api.twitter.com/2/users/by/username/{potential_username}"
                        "?user.fields=username,verified,location,description",
                        headers={
                            "Authorization": f"Bearer {self.twitter_bearer_token}"
                        },
                    )
                ) as response:
                    response = response.json()
                    if "errors" in response:
                        if "detail" in response["errors"][0]:
                            return ["Error:", response["errors"][0]["detail"]]
                        return ["User not found"]
                    user = response["data"]
                    return [
                        user["name"],
                        f"(@{user['username']}) —",
                        user["description"].replace("\n", ""),
                    ]

            return ["Twitter"]

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

    def _process_url_default(self, session, url, **kwargs):
        """Process an URL"""
        message = []
        try:
            with closing(
                session.get(url, allow_redirects=False, timeout=4, stream=True)
            ) as response:
                if response.status_code in (301, 302):
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
                    message.append("error:")
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
                    if soup.title is not None:
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
            message = []
            if len(urls) > 1:
                message.append("({})".format(index))
                index += 1
            with requests.Session() as session:
                session.headers.update(
                    {
                        "User-Agent": (
                            "linux:onebot:1 by DutchDudeWCD " "(Compatible: curl/7.61)"
                        ),
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
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
