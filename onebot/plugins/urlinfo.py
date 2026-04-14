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
import warnings
from io import StringIO
from typing import Callable, List, Optional, Self, Tuple
from urllib.parse import urlparse, parse_qs, unquote, ParseResult, urljoin

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
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


def _find_urls(string: str) -> List[str]:
    """Find all URLs in a string, stripping trailing punctuation and matching brackets."""
    urls = []
    for match in URL_PATTERN.finditer(string):
        url = match.group(0).rstrip(".,'\"")
        # Strip trailing closing brackets that don't have a matching opening bracket
        for opening, closing_bracket in [
            ("(", ")"),
            ("[", "]"),
            ("{", "}"),
            ("<", ">"),
        ]:
            while url.endswith(closing_bracket) and url.count(
                closing_bracket
            ) > url.count(opening):
                url = url[:-1]

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
        self.mediawiki_sites = self.config.get("mediawiki_sites", {})
        prefix = __name__ + ".mediawiki_sites."
        for key, value in self.bot.config.items():
            if key.startswith(prefix):
                site_name = key[len(prefix) :]
                if site_name.startswith('"') and site_name.endswith('"'):
                    site_name = site_name[1:-1]
                elif site_name.startswith("'") and site_name.endswith("'"):
                    site_name = site_name[1:-1]
                self.mediawiki_sites[site_name] = value
        self.mediawiki_logged_in = set()

        self.log.debug("Got these mediawiki sites: %s", self.mediawiki_sites)
        self.praw = None
        if "praw_client_id" in os.environ and "praw_client_secret" in os.environ:
            self.praw = praw.Reddit(user_agent=USER_AGENT_STRING, check_for_async=False)
        if reddit_client_id is not None and reddit_client_secret is not None:
            self.praw = praw.Reddit(
                client_id=reddit_client_id,
                client_secret=reddit_client_secret,
                user_agent=USER_AGENT_STRING,
                check_for_async=False,
            )

        # URL processors
        self.url_processors: List[Callable[..., Optional[list[str]]]] = [
            self._process_url_local,
            self._process_url_urlmap,
            self._process_url_mediawiki,
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
                    return ["Too many redirects"]
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
            return ["Reddit support is not enabled, API key not provided"]

        try:
            if match := REDDIT_USER_PATTERN.match(urlinfo.path):
                return [f"/u/{match.group(1)} on Reddit"]

            # Don't process media urls: I don't know how
            if urlinfo.path == "/media":
                return ["Reddit"]

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
            except praw.exceptions.InvalidURL:
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

            return ["Reddit"]

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
            raise UrlSkipException()

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
            channel = data["items"][0]["snippet"]["channelTitle"]
            duration = timedelta_format(
                parse_duration(data["items"][0]["contentDetails"]["duration"])
            )
            return [f"“{title}” ({duration}) — {channel}"]

    def _process_url_mediawiki(
        self, session: requests.Session, url: str, **kwargs
    ) -> Optional[list[str]]:
        parsed = urlparse(url)
        hostname = parsed.hostname

        # Auto-detect Wikipedia URLs (any language edition)
        if hostname and hostname.endswith(".wikipedia.org"):
            return self._process_wikipedia(session, parsed)

        if hostname not in self.mediawiki_sites:
            return None

        site_config = self.mediawiki_sites[hostname]
        api_url = site_config.get("api_url")
        if not api_url:
            return None

        title = self._mediawiki_get_title(parsed)
        if not title:
            return None

        for attempt in range(2):
            if "username" in site_config and "password" in site_config:
                if hostname not in self.mediawiki_logged_in:
                    self._mediawiki_login(
                        session,
                        api_url,
                        site_config["username"],
                        site_config["password"],
                        hostname,
                    )

            try:
                result = self._mediawiki_request_info(session, api_url, title)
                if result is None:  # Possible auth error
                    if attempt == 0:
                        self.mediawiki_logged_in.discard(hostname)
                        continue
                    return None
                return result
            except Exception as e:
                self.log.error("MediaWiki error: %s", e)
                return None

        return None

    def _process_wikipedia(
        self, session: requests.Session, parsed: ParseResult
    ) -> Optional[list[str]]:
        """Handle public Wikipedia URLs without requiring config."""
        title = self._mediawiki_get_title(parsed)
        if not title:
            return None

        api_url = f"https://{parsed.hostname}/w/api.php"
        try:
            return self._mediawiki_request_info(session, api_url, title)
        except Exception as e:
            self.log.error("Wikipedia error: %s", e)
            return None

    def _mediawiki_get_title(self, parsed_url: ParseResult) -> Optional[str]:
        """Extract MediaWiki page title from URL."""
        title = None
        if "/wiki/" in parsed_url.path:
            title = unquote(parsed_url.path.split("/wiki/", 1)[1])
        else:
            query = parse_qs(parsed_url.query)
            if "title" in query:
                title = query["title"][0]
        return title

    def _mediawiki_request_info(
        self, session: requests.Session, api_url: str, title: str
    ) -> Optional[list[str]]:
        """Request page info and extract from MediaWiki API."""
        params = {
            "action": "query",
            "prop": "extracts|info",
            "exintro": True,
            "explaintext": True,
            "titles": title,
            "format": "json",
            "redirects": True,
        }
        r = session.get(api_url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()

        if "error" in data:
            code = data["error"].get("code")
            if code in ("readapidenied", "badtoken", "mustbeloggedin"):
                self.log.info("MediaWiki access denied (%s)", code)
                return None
            return [f"MediaWiki API error: {code}"]

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return ["MediaWiki: Page not found"]

        for page_id, page in pages.items():
            if page_id == "-1":
                return ["MediaWiki: Page not found"]

            page_title = page.get("title", title)
            extract = page.get("extract", "")
            summary = ""
            if extract:
                summary = extract.strip()
                summary = summary.split("\n")[0]
                if len(summary) > 50:
                    summary = summary[:49] + "…"

            return (
                [f"“{page_title}”", f"— {summary}"] if summary else [f"“{page_title}”"]
            )

        return None

    def _mediawiki_login(self, session, api_url, username, password, hostname):
        # 1. Get Token
        try:
            r = session.get(
                api_url,
                params={
                    "action": "query",
                    "meta": "tokens",
                    "type": "login",
                    "format": "json",
                },
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()
            # If we get a "readapidenied" here, we might still be able to login via HTML
            # checking error code is tricky because some private wikis return it in 'error' field
            # but allow token fetching sometimes?
            # Actually, my test showed token fetching worked.

            if "error" in data and data["error"].get("code") == "readapidenied":
                # If we can't even get a token, try HTML login immediately?
                # But wait, my test showed I GOT a token, then failed on POST.
                pass

            login_token = data.get("query", {}).get("tokens", {}).get("logintoken")
            if not login_token:
                self.log.warning("Could not get login token for %s", api_url)
                # Fallback to HTML login
                return self._mediawiki_login_html(
                    session, api_url, username, password, hostname
                )

            # 2. Post Login
            r = session.post(
                api_url,
                data={
                    "action": "login",
                    "lgname": username,
                    "lgpassword": password,
                    "lgtoken": login_token,
                    "format": "json",
                },
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()

            if "error" in data and data["error"].get("code") == "writeapidenied":
                self.log.warning(
                    "Write API denied for %s, trying HTML login fallback", api_url
                )
                return self._mediawiki_login_html(
                    session, api_url, username, password, hostname
                )

            login_result = data.get("login", {}).get("result")
            if login_result == "Success":
                self.log.info("Logged in to MediaWiki %s", api_url)
                self.mediawiki_logged_in.add(hostname)
                # Update self.cookiejar to persist?
                if self.cookiejar:
                    self.cookiejar.update(session.cookies)
                else:
                    self.cookiejar = session.cookies
            else:
                self.log.warning(
                    "Failed to login to MediaWiki %s: %s", api_url, login_result
                )
                # Fallback
                self._mediawiki_login_html(
                    session, api_url, username, password, hostname
                )

        except Exception as e:
            self.log.error("MediaWiki login failed: %s", e)
            self._mediawiki_login_html(session, api_url, username, password, hostname)

    def _mediawiki_login_html(self, session, api_url, username, password, hostname):
        """Fallback login via HTML form."""
        self.log.debug("Attempting HTML login fallback for %s", api_url)
        if api_url.endswith("api.php"):
            base_url = api_url[:-7]  # strip 'api.php'
            login_url = base_url + "index.php?title=Special:UserLogin"
        else:
            self.log.warning("Cannot deduce login URL from %s", api_url)
            return

        try:
            r = session.get(login_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, "html.parser")

            inputs = {}
            for inp in soup.find_all("input"):
                if inp.get("name"):
                    inputs[inp.get("name")] = inp.get("value", "")

            inputs["wpName"] = username
            inputs["wpPassword"] = password
            inputs["wploginattempt"] = "Log in"

            form = soup.find("form", action=True)
            if not form:
                self.log.warning("No login form found at %s", login_url)
                return

            action = form.get("action")
            # Handle relative URL
            action = urljoin(login_url, action)

            r = session.post(action, data=inputs, timeout=10)
            r.raise_for_status()

            if "Log out" in r.text or "Special:UserLogout" in r.text:
                self.log.info("Logged in to MediaWiki %s via HTML", api_url)
                self.mediawiki_logged_in.add(hostname)
                if self.cookiejar:
                    self.cookiejar.update(session.cookies)
                else:
                    self.cookiejar = session.cookies
            else:
                self.log.warning("HTML Login failed for %s", api_url)

        except Exception as e:
            self.log.error("HTML Login exception: %s", e)

    def _process_url_default(
        self, session: requests.Session, url: str, **kwargs
    ) -> list[str]:
        """Default URL processor: fetches the page and extracts its title or metadata."""
        try:
            with closing(
                session.get(url, allow_redirects=False, timeout=4, stream=True)
            ) as response:
                if response.status_code in (301, 302, 307, 308):
                    if response.next and response.next.url:
                        raise UrlRedirectException(response.next.url)

                return self._handle_default_response(response)
        except UrlRedirectException:
            raise
        except requests.exceptions.Timeout:
            self.log.debug("Timeout while requesting %s", url)
            return ["Timeout"]
        except Exception:
            self.log.exception("Error in _process_url_default for %s", url)
            return []

    def _handle_default_response(self, response: requests.Response) -> list[str]:
        """Handle the response from the default URL processor."""
        content_type = response.headers.get("Content-Type", "text/html").split(";")[0]
        size_header = response.headers.get("Content-Length")
        size = int(size_header) if size_header else 0

        content = None
        if size == 0:
            size, content = _read_body(response)

        self.log.debug("File size: %s, Content-Type: %s", size, content_type)

        if not response.ok:
            return [f"error: HTTP {response.status_code}", response.reason.lower()]

        if size < 0:
            return ["Safety error: unknown size, not reading"]

        if content_type not in ("text/html", "application/xhtml+xml"):
            return self._format_metadata(content_type, size)

        if size < (1048576 * 2):
            html_content = content or response.content.decode("utf-8", "ignore")
            self.log.debug("HTML content length: %s", len(html_content))
            return self._extract_title_from_content(html_content)

        return []

    def _format_metadata(self, content_type: str, size: int) -> list[str]:
        """Format metadata for non-HTML files."""
        try:
            class_, app = content_type.split("/", 1)
        except ValueError:
            class_, app = content_type, ""

        if (class_ in self.ignored_classes or app in self.ignored_apps) and size < (
            1048576 * 5
        ):
            return []

        return ["Content-Type:", content_type, "Filesize:", sizeof_fmt(size)]

    def _extract_title_from_content(self, content: str) -> list[str]:
        """Extract a title from HTML content, preferring og:title over <title>."""
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(content, "html.parser")
        og_tag = soup.find("meta", property="og:title")
        title = (" ".join(og_tag.get("content", "").split()) if og_tag else "") or (
            " ".join(soup.title.get_text().split()) if soup.title else ""
        )
        if not title:
            return []
        if len(title) > 320:
            title = f"{title[:310]}…"
        return [f"“{title}”"]

    @event(
        r"^:(?P<mask>\S+!\S+@\S+) (?P<event>(PRIVMSG|NOTICE)) "
        r"(?P<target>\S+) :\s*(?P<data>(.*(https?://)).*)$"
    )
    def on_message(self, mask, event, target, data):
        if not self._should_process_message(mask, event, target):
            return

        urls = list(dict.fromkeys(_find_urls(data)))
        if not urls:
            return

        messages = self._process_urls(urls)
        if messages:
            response = "{}.".format(" ".join(messages))
            self.bot.privmsg(target, self.bot.redact_nicks(response, target=target))

    def _should_process_message(self, mask, event, target) -> bool:
        """Determine if a message should be processed for URLs."""
        return not (
            mask.nick == self.bot.nick
            or event == "NOTICE"
            or not target.is_channel
            or target in self.ignored_channels
            or mask.nick in self.ignored_nicks
        )

    def _process_urls(self, urls: List[str]) -> List[str]:
        """Process a list of URLs and return formatted messages."""
        messages = []
        with requests.Session() as session:
            for index, url in enumerate(urls, 1):
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
                    url_msg_parts = self._process_url(session, url)
                    if url_msg_parts:
                        prefix = f"({index}) " if len(urls) > 1 else ""
                        messages.append(f"{prefix}{' '.join(url_msg_parts)}")
                except Exception:
                    self.log.exception("Exception while requesting %s", url)

        return messages

    @classmethod
    def reload(cls, old: Self) -> Self:  # pragma: no cover
        return cls(old.bot)
