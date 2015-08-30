# -*- coding: utf-8 -*-
"""Show info about posted URLs

"""

import re
import pickle
import socket
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests
import requests.exceptions
from irc3 import plugin, event


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


@plugin
class UrlInfo(object):
    """Bot User Interface plugin"""

    def __init__(self, bot):
        """Init"""
        self.bot = bot
        self.config = bot.config.get(__name__, {})
        self.log = self.bot.log.getChild(__name__)
        cookiejar_file = self.config.get('cookiejar')
        if cookiejar_file:
            with open(cookiejar_file, 'rb') as f:
                self.cookiejar = pickle.load(f)

        self.urlmap = self.bot.config.get(__name__ + '.urlmap', {})

    @event('^:(?P<mask>\S+!\S+@\S+) (?P<event>(PRIVMSG|NOTICE)) '
           '(?P<target>\S+) :\s*(?P<data>(.*(https?://)).*)$')
    def on_message(self, mask, event, target, data):
        if mask.nick == self.bot.nick or event == 'NOTICE':
            return
        index = 1
        urls = re.findall(r'https?://\S+', data)
        for url in urls:
            message = ["URL:"]
            o = urlparse(url)
            if o.hostname in ('127.0.0.1', '[::1]',
                              'localhost',
                              'localhost.localdomain',
                              socket.gethostname()):
                continue
            if o.hostname in self.urlmap:
                url = url.replace(o.hostname, self.urlmap[o.hostname], 1)
                message.append(url)
            with requests.Session() as session:
                session.cookies = self.cookiejar
                self.log.debug("processing %s", url)
                if len(urls) > 1:
                    message.append("({})".format(index))
                    index += 1
                try:
                    response = session.head(
                        url, allow_redirects=True, timeout=3)
                    content_type = response.headers.get(
                        'Content-Type', 'text/html').split(';')[0]
                    if not response.ok:
                        message.append("error:")
                        message.append(response.reason.lower())
                    elif content_type not in (
                            'text/html', 'application/xhtml+xml'):
                        message.append("type:")
                        message.append(response.headers['Content-Type'])
                        message.append("size:")
                        message.append(sizeof_fmt(
                            int(response.headers['Content-Length'])))
                    else:
                        result = session.get(
                            url, allow_redirects=True, timeout=4)
                        soup = BeautifulSoup(result.content, 'html.parser')
                        if hasattr(soup, 'title'):
                            message.append("title:")
                            message.append(
                                "“{}”".format(soup.title.string))
                except requests.exceptions.Timeout:
                    message.append("error: timeout")
                    self.log.debug("Error while requesting %s", url)
                except:
                    self.log.exception(
                        "Exception while requesting %s", url)
                    continue

            self.bot.privmsg(target, "{}.".format(' '.join(message)))
