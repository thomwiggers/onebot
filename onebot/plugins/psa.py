# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.psa` PSA
================================================

This plugin allows admins to send broadcasts
"""

from irc3 import plugin
from irc3.plugins.command import command


@plugin
class PSAPlugin(object):
    """PSA Plugin"""

    requires = [
        'irc3.plugins.command',
        'irc3.plugins.userlist',
    ]

    def __init__(self, bot):
        self.bot = bot
        self._config = bot.config.get(__name__, {})
        self._admin = self._config.get('admin', '')

    @command(permission='admin', show_in_help_list=False)
    def psa(self, mask, target, args):
        """Broadcast a public service announcement to all channels

            %%psa <message>...
        """
        for channel in self.bot.channels:
            self.bot.privmsg(channel, ' '.join(args['<message>']))
