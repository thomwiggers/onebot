# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.psa` PSA
================================================

This plugin allows admins to send broadcasts
"""

from irc3.plugins.command import command
from irc3 import plugin


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
        self._log = self.bot.log.getChild(__name__)

    @command(permission='admin', show_in_help_list=False)
    def psa(self, mask, target, args):
        """Broadcast a public service announcement to all channels

            %%psa <message>...
        """
        self._log.info("%s annouced PSA: %s " % (mask.nick,
            ' '.join(args['<message>'])))
        for channel in self.bot.channels:
            self.bot.privmsg(channel, ' '.join(args['<message>']))
