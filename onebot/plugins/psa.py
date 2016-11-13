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

    @command(permission='admin', show_in_help_list=False)
    def psa(self, mask, target, args):
        """Broadcast a public service announcement to all channels

            %%psa [<message>...]
        """
        msg = ' '.join(args['<message>'] or [])
        if not msg:
            self.bot.privmsg(mask.nick, "I need a message to announce")
        # FIXME channels are only listed if activity (i.e. join, part) is
        # recorded in them first, not a list of channels the bot is in.
        else:
            for channel in self.bot.channels:
                self.bot.privmsg(channel, msg)
