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
from io import StringIO
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests
import requests.exceptions
from irc3 import plugin, event


def sizeof_fmt(num, suffix='B'):
    """Format printable versions for bytes"""
    if num == -1:
        return "large"
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def _read_body(response):
    """Count the size of the body of files"""
    content = StringIO()
    size = 0
    for chunk in response.iter_content(1048576):
        if size < 5 * 1048576:
            content.write(chunk.decode('utf-8', 'ignore'))
        elif size > 30 * 1048576:
            response.close()
            return -1, None
        size += len(chunk)

    return size, content.getvalue()


URL_PATTERN = re.compile(r'\bhttps?://\S+')


def _find_urls(string):
    """Find all urls in a string"""
    urls = []
    for match in URL_PATTERN.finditer(string):
        url = match.group(0).rstrip('.,\'"')
        # Find matching pairs, strip others
        for lbr, rbr in [('(', ')'),
                         ('[', ']'),
                         ('{', '}'),
                         ('<', '>')]:
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


@plugin
class UrlInfo(object):
    """Bot User Interface plugin

    Configuration settings:
        - ``cookiejar``: Cookies to identify to sites with
        - ``ignored_classes``: ignored MIME classes
        - ``ignored_apps``: ignored ``application/`` classes
        - ``ignored_channels``: channels to not post information in
        - ``ignored_nicks``: whom to ignore

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
        cookiejar_file = self.config.get('cookiejar')
        self.ignored_classes = self.config.get('ignored_classes',
                                               ['image', 'text'])
        self.ignored_apps = self.config.get('ignored_apps', ['pdf'])
        self.ignored_channels = self.config.get('ignored_channels', [])
        self.ignored_nicks = self.config.get('ignored_nicks', [])
        self.cookiejar = None
        if cookiejar_file:
            with open(cookiejar_file, 'rb') as f:
                self.cookiejar = pickle.load(f)

        self.urlmap = self.bot.config.get(__name__ + '.urlmap', {})

        # URL processors
        self.url_processors = [
            self._process_url_urlmap,
            self._process_url_reddit,
        ]

    def _process_url(self, session, url, **kwargs):
        try:
            # filter out private addresses
            # May raise exceptions
            for (f, t, p, c, sockaddr) in socket.getaddrinfo(
                    urlparse(url).hostname, None):
                ip = ipaddress.ip_address(sockaddr[0])
                if (ip.is_private or ip.is_loopback or
                        ip.is_link_local or ip.is_reserved):
                    return
        except Exception:
            return

        for function in self.url_processors:
            try:
                result = function(session, url, **kwargs)
            except UrlSkipException:
                return
            if result:
                return result

        return self._process_url_default(session, url)

    def _process_url_urlmap(self, session, url, already_extended=False):
        # FIXME what does this even do
        if already_extended:
            return
        o = urlparse(url)
        if o.hostname in self.urlmap:
            url = url.replace(o.hostname, self.urlmap[o.hostname], 1)
            return [url].extend(
                self._process_url(session, url, already_extended=True) or [])

    def _process_url_reddit(self, session, url):
        """Skip reddit urls for now because they are unreliable
        FIXME
        """
        if urlparse(url).hostname.endswith('reddit.com'):
            raise UrlSkipException()

    def _process_url_default(self, session, url):
        """Process an URL"""
        message = []
        try:
            with closing(
                    session.get(url, allow_redirects=True,
                                timeout=4, stream=True)) as response:
                content_type = response.headers.get(
                    'Content-Type', 'text/html').split(';')[0]
                size = int(response.headers.get('Content-Length', 0))

                # handle chunked transfers
                content = None
                if size == 0:
                    size, content = _read_body(response)

                self.log.debug("File size: {}".format(repr(size)))
                if not response.ok:
                    message.append("error:")
                    message.append(response.reason.lower())
                elif size < 0:
                    message.append(
                        "Safety error: unknown size, not reading")
                elif (content_type not in (
                        'text/html', 'application/xhtml+xml')):
                    class_, app = content_type.split('/')
                    if not ((class_ in self.ignored_classes or
                             app in self.ignored_apps) and
                            size < (1048576 * 5)):
                        message.append("Content-Type:")
                        message.append(content_type)
                        message.append("Filesize:")
                        message.append(sizeof_fmt(size))
                elif size < (1048576 * 2):
                    soup = BeautifulSoup(
                        (content or
                         response.content.decode('utf-8', 'ignore')),
                        'html5lib')
                    if soup.title is not None:
                        title = soup.title.string.strip()
                        if len(title) > 320:
                            title = "{}…".format(title[:310])
                        message.append(
                            "“{}”".format(title))
            # endwith
        except requests.exceptions.Timeout:
            self.log.debug("Error while requesting %s", url)
            message.append('Timeout')
        return message

    @event('^:(?P<mask>\S+!\S+@\S+) (?P<event>(PRIVMSG|NOTICE)) '
           '(?P<target>\S+) :\s*(?P<data>(.*(https?://)).*)$')
    def on_message(self, mask, event, target, data):
        if (mask.nick == self.bot.nick or event == 'NOTICE' or
                not target.is_channel or target in self.ignored_channels or
                mask.nick in self.ignored_nicks):
            return
        index = 1
        messages = []
        urls = _find_urls(data)
        for url in urls:
            message = []
            if len(urls) > 1:
                message.append("({})".format(index))
                index += 1
            with requests.Session() as session:
                session.headers.update(
                    {'User-Agent': "linux:onebot:1 by DutchDudeWCD",
                     'Accept-Language': 'en-GB, en-US, en, nl-NL, nl'})
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
                    self.log.exception(
                        "Exception while requesting %s", url)
                    continue
                # end try
            # end with session
            if message:
                messages.append(' '.join(message))
        if messages:
            self.bot.privmsg(target, "{}.".format(' '.join(messages)))

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
