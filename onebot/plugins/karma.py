# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.karma` Karma
================================================

This plugin keeps track of karma.

To modify: foo++ / (foo bar)++ / foo--
To view: !karma foo bar
"""

import base64
import irc3
from irc3 import plugin
from irc3.plugins.command import command


def _format_key(key):
    return 'karma_{}'.format(base64.b64encode(key.lower().encode('utf-8')))


def _find_key(data, modifier='++'):
    # This assumes that `modifier' is present in `data'
    data = data[:data.find(modifier)]
    if data[-1] == ')' and '(' in data:
        key = data.split('(')[-1][:-1]
    else:
        key = data.split(' ')[-1]
    return _format_key(key)


@plugin
class KarmaPlugin(object):
    """Karma Plugin"""

    requires = [
        'irc3.plugins.storage',
        'irc3.plugins.command',
    ]

    def __init__(self, bot):
        self.bot = bot

    def _update_karmadict(self, karmakey, field):
        karma = {'up': 0, 'down': 0}
        if karmakey in self.bot.db:
            karma = self.bot.db[karmakey]
        karma[field] += 1
        self.bot.db[karmakey] = karma

    @irc3.event((r'''(@(?P<tags>\S+) )?:(?P<mask>\S+) (PRIVMSG)'''
                 r''' (?P<target>\S+)(\s:(?P<data>.+)|$)'''))
    def modify(self, mask, target=None, data=None, **kwargs):
        for mod, token in [('up', '++'), ('down', '--')]:
            message = data
            while message.find(token) > -1:
                karmakey = _find_key(message, token)
                self._update_karmadict(karmakey, mod)
                message = message[message.find(token) + len(token):]

    @command
    def karma(self, mask, target, args):
        """Get the karma of a certain key

            %%karma <terms>...
        """
        key = ' '.join(args['<terms>'])
        karmakey = _format_key(key)
        if karmakey in self.bot.db:
            karma = self.bot.db[karmakey]
            yield "'{}' has a karma of {} ({}, {})".format(
                key, karma['up'] - karma['down'], karma['up'], karma['down'])
        else:
            yield "No karma stored for '{}'".format(key)

    @classmethod
    def reload(cls, old):
        return cls(old.bot)
