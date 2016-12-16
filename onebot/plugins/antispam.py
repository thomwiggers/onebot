# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.antispam` PSA
================================================

This plugin attempts to combat spam

Config options:
    max_highlights      Maximum number of nicks before kick (default: 5)

"""

import asyncio
from collections import defaultdict
import hashlib

from irc3 import rfc, plugin
from irc3.dec import event


def _hash(string):
    h = hashlib.sha256()
    h.update(string.encode())
    return h.hexdigest()


@plugin
class PSAPlugin(object):
    """PSA Plugin"""

    requires = [
        'irc3.plugins.userlist',
        'onebot.plugins.users'
    ]

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config.get(self.__class__.__module__, {})
        self.max_highlights = self.config.get('max_highlights', 5)
        self.max_repeats = self.config.get('max_repeats', 5)
        self.log = self.bot.log.getChild(__name__)
        self.lastlines = defaultdict(dict)

    @event(rfc.PRIVMSG)
    def nickspamfilter(self, mask, target, data, **kwargs):
        """Kicks people who highlight lots of users"""
        highlights = 0
        words = data.split()
        if target in self.bot.channels:
            for nick in self.bot.channels[target]:
                if nick in words:
                    highlights += 1
                if highlights >= self.max_highlights:
                    self.log.info("Kicking {} for highlightspam", mask.nick)
                    self.bot.kick(target, mask.nick,
                                  "Don't excessively highlight people.")
                    return

    @asyncio.coroutine
    @event(rfc.PRIVMSG)
    def repeatingspam(self, mask, target, data, **kwargs):
        user = self.bot.get_user(mask.nick)
        data = _hash(target + data.strip())
        last_line = yield from user.get_setting('last_line')
        num = yield from user.get_setting('last_line_num')
        if data == last_line:
            num += 1
            if num >= self.max_repeats:
                self.log.info("Kicking {} for spamming", mask.nick)
                self.bot.kick(target, mask.nick,
                              "Try to come up with something more creative. "
                              "({} repeating lines)".format(num))
        else:
            user.set_setting('last_line', data)
            num = 1
        user.set_setting('last_line_num', num)

    @classmethod
    def reload(cls, old):
        return cls(old.bot)
