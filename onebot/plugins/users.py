# -*- coding: utf8 -*-
"""
==============================================
:mod:`onebot.plugins.users` Users plugin
==============================================

Keeps track of the users in channels. Also provides an authorisation system.
This plugin uses WHOIS to figure out someones NickServ account and then links
that to an automatically created, in-bot account.
"""

from __future__ import unicode_literals, print_function

import irc3


class User(object):
    """User object"""

    def __init__(self, mask, channels, id_):
        self.nick = mask.nick
        self.host = mask.host
        self.channels = set()
        self._id = id_
        try:
            for c in iter(channels):
                self.channels.add(c)
        except TypeError:
            raise ValueError("You need to specify in which channel this "
                             "user is!")

    @property
    def mask(self):
        return irc3.utils.IrcString('{}!{}'.format(self.nick, self.host))

    def join(self, channel):
        self.channels.add(channel)

    def part(self, channel):
        self.channels.remove(channel)

    def still_in_channels(self):
        return len(self.channels) > 0

    def getid(self):
        return self._id

    def __eq__(self, user):
        return self.nick == user.nick


@irc3.plugin
class UsersPlugin(object):
    """User management plugin for OneBot"""

    requires = [
        'onebot.plugins.database'
    ]

    def __init__(self, bot):
        """Initialises the plugin"""
        self.bot = bot
        config = bot.config.get(__name__, {})
        self.identifying_method = config.get('identify_by', 'mask')

        self.connection_lost()

    @irc3.extend
    def get_user(self, nick):
        return self.active_users[nick]

    @irc3.event(irc3.rfc.JOIN_PART_QUIT)
    def on_join_part_quit(self, mask=None, event=None, **kwargs):
        self.bot.log.debug("%s %sed", mask.nick, event)
        getattr(self, event.lower())(mask.nick, mask, **kwargs)

    @irc3.event(irc3.rfc.KICK)
    def on_kick(self, mask=None, event=None, target=None, **kwargs):
        self.bot.log.debug("%s kicked %s", mask.nick, target.nick)
        self.part(target.nick, target, **kwargs)

    @irc3.event(irc3.rfc.NEW_NICK)
    def on_new_nick(self, nick=None, new_nick=None, **kwargs):
        self.bot.log.debug("%s renamed to %s", nick.nick, new_nick)
        if nick.nick in self.active_users:
            user = self.active_users[nick.nick]
            user.nick = new_nick
            self.active_users[new_nick] = user
            del self.active_users[nick.nick]

    def connection_lost(self):
        self.channels = set()
        self.active_users = dict()

    def join(self, nick, mask, **kwargs):
        channel = kwargs['channel']

        # This can only be observed if we're in that channel
        self.channels.add(kwargs['channel'])

        if nick not in self.active_users:
            self.active_users[nick] = self.create_user(mask, [channel])

        self.active_users[nick].join(channel)

    def quit(self, nick, mask, **kwargs):
        if nick == self.bot.nick:
            self.connection_lost()

        if nick in self.active_users:
            del self.active_users[nick]

    def part(self, nick, mask, **kwargs):
        if nick not in self.active_users:
            return

        if nick == self.bot.nick:
            for (n, user) in self.active_users.items():
                user.part(kwargs['channel'])
                if not user.still_in_channels:
                    del self.active_users[n]
                self.channels.remove(kwargs['channel'])

        self.active_users[nick].part(kwargs['channel'])
        if not self.active_users[nick].still_in_channels():
            self.bot.log.debug("Lost {} out of sight", mask.nick)
            del self.active_users[nick]

    @irc3.event(irc3.rfc.RPL_WHOREPLY)
    def on_who(self, channel=None, nick=None, username=None, server=None,
               **kwargs):
        """Process a WHO reply since it could contain new information.

        Should only be processed for channels we are currently in!
        """
        if channel not in self.channels:
            return

        if nick not in self.active_users:
            mask = irc3.utils.IrcString('{}!{}@{}'.format(
                nick, username, server))
            self.active_users[nick] = self.create_user(mask, [channel])
        else:
            self.active_users[nick].join(channel)

    def create_user(self, mask, channels):
        """Return a User object"""
        if self.identifying_method == 'mask':
            return User(mask, channels, mask.host)
        else:  # pragma: no cover
            raise ValueError("A valid identifying method should be configured")
