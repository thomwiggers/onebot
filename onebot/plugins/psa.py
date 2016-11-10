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

    @command(permission='admin', show_in_help_list=False)
    def psa(self, mask, target, args):
        """Broadcast a public service announcement to all channels

            %%psa <message>...
        """
        msg = ' '.join(args['<message>'] or [])
        for channel in self.bot.channels:
            self.bot.privmsg(channel, msg)
