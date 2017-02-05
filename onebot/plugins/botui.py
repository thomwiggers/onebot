# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.botui` Bot Control plugin
================================================

This plugin implements some utility commands.

Based on http://git.io/v3HVL by gawel
"""


from irc3.plugins.command import command
from irc3 import plugin, event


@plugin
class BotUI(object):
    """Bot User Interface plugin

    Configuration settings:
        - ``joininvite``: Should I join when invited
        - ``admin``: Who to message when invited
    """

    def __init__(self, bot):
        """Init"""
        self.bot = bot
        self._config = bot.config.get(__name__, {})
        self._log = self.bot.log.getChild(__name__)

        self._autojoin = self._config.get('joininvite', False)
        self._admin = self._config.get('admin', '')

    @event(r'^:(?P<sender>\S+?)!\S+ INVITE (?P<target>\S+) '
           r'(?P<channel>#\S+)', iotype="in")
    def onInvite(self, sender=None, target=None, channel=None):
        """Will send a message to the admin or automatically join a channel
        when it gets invited."""
        self._log.info("%s invited me to %s." % (sender, channel))

        if self._autojoin:
            if target.nick == self.bot.nick:
                self.bot.join(channel)
        else:
            self.bot.privmsg(
                sender,
                "Never accept an invitation from a stranger unless he gives "
                "you candy. -- Linda Festa")
            if self._admin:
                self.bot.notice(self._admin,
                                "%s invited me to %s." % (sender, channel))

    @command(permission="operator", show_in_help_list=False)
    def join(self, mask, target, args):
        """
        Join - Command the bot to join a channel.

            %%join <channel> [<password>]
        """

        channel = args['<channel>']

        if args['<password>'] is not None:
            channel += " %s" % args['<password>']

        self.bot.join(channel)

    @command(permission="operator", show_in_help_list=False)
    def part(self, mask, target, args):
        """
        Part - Command the bot to leave a channel

            %%part [<channel>]
        """

        if args['<channel>'] is not None:
            target = args['<channel>']

        self.bot.part(target)

    @command(permission='admin', show_in_help_list=False)
    def quit(self, mask, target, args):
        """
        Quit - Shutdown the bot

            %%quit [<reason>...]
        """
        reason = ' '.join(args['<reason>'] or [])
        self.bot.quit('{} -- {}'.format(reason, mask.nick).strip())
        self.bot.loop.stop()

    @command(permission='admin', show_in_help_list=False)
    def nick(self, mask, target, args):
        """
        Nick - Change nickname of the bot

            %%nick <nick>
        """

        self.bot.set_nick(args['<nick>'])

    @command(permission='operator', show_in_help_list=False)
    def mode(self, mask, target, args):
        """
        Mode - Set user mode for the bot.

            %%mode <mode-cmd>
        """

        self.bot.mode(self.bot.nick, args['<mode-cmd>'])

    @command(permission='admin', show_in_help_list=False)
    def msg(self, mask, target, args):
        """
        Msg - Send a message

            %%msg <target> <message>...
        """

        msg = ' '.join(args['<message>'] or [])
        self.bot.privmsg(args['<target>'], msg)

    @command(permission='admin', show_in_help_list=False)
    def quote(self, mask, target, args):
        """Send a raw string to the ircd

           %%quote <string>...
        """
        cmd = ' '.join(args['<string>'] or [])
        self.bot.privmsg(target, "Sending {}".format(cmd))
        self.bot.send(cmd)

    @command(name='reload', permission='admin', show_in_help_list=False)
    def reload_cmd(self, mask, target, args):
        """Reload - Reloads a plugin and the config file without restarting the IrcBot

          %%reload <plugin>
        """
        self.bot.registry.includes

        if ''.join(args['<plugin>']) in self.bot.registry.includes:
            self.bot.reload(args['<plugin>'])
            self.bot.privmsg(target, "{} reloaded".format(args['<plugin>']))
        else:
            self.bot.privmsg(target, "{} not a valid plugin".format(
                args['<plugin>']))

    @command(permission='admin', show_in_help_list=False)
    def restart(self, mask, target, args):
        """Quit the IRC bot with an error code to signal restart

          %%restart [<reason>...]
        """
        import sys
        reason = ' '.join(args['<reason>'] or [])
        self.bot.quit('{} -- {} (restart)'.format(reason, mask.nick).strip())
        self.bot.loop.stop()
        sys.exit(2)

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
