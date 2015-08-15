# -*- coding: utf-8 -*-
"""Bot control

Based on http://git.io/v3HVL by gawel
"""


from irc3.plugins.command import command
from irc3 import plugin, event
import logging


@plugin
class BotUI(object):
    """Bot User Interface plugin"""

    def __init__(self, bot):
        """Init"""
        self._bot = bot
        self._config = bot.config.get(__name__, {})
        self._log = self.bot.log.getChild(__name__)

        if self._bot.config.get('verbose'):
            self._log.setLevel(logging.DEBUG)
        else:
            level = self._bot.config.get('level')

            if level is not None:
                level = getattr(logging, str(level), level)
                self._log.setLevel(level)

        self._autojoin = self._config.get('joininvite', False)
        self._admin = self._config.get('admin', '')

    @event(r'^:(?P<sender>\S+?)!\S+ INVITE (?P<target>\S+) '
           r'(?P<channel>#\S+)', iotype="in")
    def onInvite(self, sender=None, target=None, channel=None):
        """Will send a message to the admin or automatically join a channel
        when it gets invited."""
        self._log.info("%s invited me to %s." % (sender, channel))

        if self._autojoin:
            if target == self._bot.nick:
                self._bot.join(channel)
        else:
            self.bot.privmsg(
                sender,
                "Never accept an invitation from a stranger unless he gives "
                "you candy. -- Linda Festa")
            if self._admin:
                self._bot.notice(self._admin,
                                 "%s invited me to %s." % (sender, channel))

    @command(permission="operator")
    def join(self, mask, target, args):
        """
        Join - Command the bot to join a channel.
        %%join <channel> [<password>]
        """

        channel = args['<channel>']

        if args['<password>'] is not None:
            channel += " %s" % args['<password>']

        self._bot.join(channel)

    @command(permission="operator")
    def part(self, mask, target, args):
        """
        Part - Command the bot to leave a channel
        %%part [<channel>]
        """

        if args['<channel>'] is not None:
            target = args['<channel>']

        self._bot.part(target)

    @command(permission='admin')
    def quit(self, mask, target, args):
        """
        Quit - Shutdown the bot
        %%quit [<reason>]
        """

        self._bot.quit(args['<reason>'])
        self._bot.loop.stop()

    @command(permission='admin')
    def nick(self, mask, target, args):
        """
        Nick - Change nickname of the bot
        %%nick <nick>
        """

        self._bot.set_nick(args['<nick>'])

    @command(permission='operator')
    def mode(self, mask, target, args):
        """
        Mode - Set user mode for the bot.

        %%mode <mode cmd>
        """

        self._bot.mode(self._bot.nick, args['<mode cmd>'])

    @command(permission='admin')
    def msg(self, mask, target, args):
        """
        Msg - Send a message

        %%msg <target> <message>
        """

        self._bot.privmsg(args['<target>'], args['<message>'])

    @command(permission='admin')
    def quote(self, mask, target, args):
        """Send a raw string to the ircd

        %%quote <string>
        """
        self._bot.send(args['<string>'])
