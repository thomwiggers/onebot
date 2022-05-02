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

import ast
import asyncio
import re
from typing import Any, Dict, List, Optional, Set

import irc3
from irc3.plugins.storage import Storage
from irc3.utils import IrcString


class User(object):
    """User object"""

    def __init__(self, mask, channels: List[str], id_, database=None):
        self.nick = mask.nick
        self.host = mask.host
        self.channels: Set[str] = set()
        self.id = id_
        self.database: Optional[Storage] = database
        try:
            if isinstance(channels, str):
                raise ValueError("You must specify a list of channels!")
            for c in iter(channels):
                self.channels.add(c)
        except TypeError:
            raise ValueError("You need to specify in which channel this " "user is!")

    @property
    def mask(self) -> IrcString:
        """Get the mask of this user"""
        return IrcString("{}!{}".format(self.nick, self.host))

    def _get_database(self) -> Storage:
        if self.database is None:
            raise Exception("No database set for this user.")
        return self.database

    def set_settings(self, settings):
        """Replaces the settings with the provided dictionary"""

        async def wrapper():
            id_ = await self.id()
            self._get_database()[id_] = settings

        asyncio.ensure_future(wrapper())

    def set_setting(self, setting: str, value: Any):
        """Set a specified setting to a value"""
        print("Trying to set %s to %s" % (setting, value))

        async def wrapper():
            id_ = await self.id()
            self._get_database().set(id_, **{setting: value})

        asyncio.ensure_future(wrapper())

    async def get_settings(self) -> Dict[str, Any]:
        """Get this users settings"""
        id_ = await self.id()
        return self._get_database().get(id_, dict())

    async def get_setting(self, setting, default=None) -> Any:
        """Gets a setting for the users. Can be any type."""
        settings = await self.get_settings()
        result = settings.get(setting, default)
        if isinstance(result, str):
            try:
                parsed = ast.literal_eval(result)
                return parsed
            except (ValueError, SyntaxError):
                pass

        return result

    def join(self, channel) -> None:
        """Register that the user joined a channel"""
        self.channels.add(channel)

    def part(self, channel) -> None:
        """Register that the user parted a channel"""
        self.channels.remove(channel)

    def still_in_channels(self) -> bool:
        """Is the user still in channels?"""
        return len(self.channels) > 0

    def __eq__(self, other: object) -> bool:
        """Compare users by nick

        Since nicks are unique this works for exactly one irc server.
        """
        if not isinstance(other, self.__class__):
            return False
        return self.nick == other.nick


@irc3.plugin
class UsersPlugin(object):
    """User management plugin for OneBot

    Doesn't do anything with NAMES because we can't get hosts through
    NAMES

    Configuration settings:
        - ``identify_by``: the identification method

    Identification methods available:
        - ``mask``: Use the hostmask
        - ``whatcd``: Get the what.cd username from the host mask
        - ``nickserv``: Parse nickserv info from ``WHOIS``.
    """

    requires = ["irc3.plugins.storage", "irc3.plugins.asynchronious"]

    def __init__(self, bot: irc3.IrcBot):
        """Initialises the plugin"""
        self.bot = bot
        config = bot.config.get(__name__, {})
        self.identifying_method = config.get("identify_by", "mask")
        self.log = bot.log.getChild(__name__)
        self.connection_lost()

    @irc3.extend
    def get_user(self, nick):
        user = self.active_users.get(nick)
        if not user:
            self.log.warning("Couldn't find %s!", nick)
        return user

    @irc3.event(irc3.rfc.JOIN_PART_QUIT)
    def on_join_part_quit(self, mask=None, **kwargs):
        event = kwargs["event"]
        self.log.debug("%s %sed", mask.nick, event.lower())
        getattr(self, event.lower())(mask.nick, mask, **kwargs)

    @irc3.event(irc3.rfc.KICK)
    def on_kick(self, mask=None, target=None, **kwargs):
        self.log.debug("%s kicked %s", mask.nick, target.nick)
        self.part(target.nick, target, **kwargs)

    @irc3.event(irc3.rfc.NEW_NICK)
    def on_new_nick(self, nick=None, new_nick=None, **kwargs):
        self.log.debug("%s renamed to %s", nick.nick, new_nick)
        if nick.nick in self.active_users:
            user = self.active_users[nick.nick]
            user.nick = new_nick
            del self.active_users[nick.nick]
            self.active_users[new_nick] = user

    @irc3.event(irc3.rfc.PRIVMSG)
    def on_privmsg(self, mask=None, event=None, target=None, data=None):
        if target not in self.channels:
            return
        if mask.nick not in self.active_users:
            self.log.debug("Found user %s via PRIVMSG", mask.nick)
            self.active_users[mask.nick] = self.create_user(mask, [target])
        else:
            self.active_users[mask.nick].join(target)

    def connection_lost(self):
        self.channels = set()
        self.active_users = dict()

    def join(self, nick, mask, channel=None, **kwargs):
        self.log.debug("%s joined channel %s", nick, channel)
        # This can only be observed if we're in that channel
        self.channels.add(channel)
        if nick == self.bot.nick:
            self.bot.send("WHO {}".format(channel))

        if nick not in self.active_users:
            self.active_users[nick] = self.create_user(mask, [channel])

        self.active_users[nick].join(channel)

    def quit(self, nick, _mask, **kwargs):
        if nick == self.bot.nick:
            self.connection_lost()

        if nick in self.active_users:
            del self.active_users[nick]

    def part(self, nick, mask, channel=None, **kwargs):
        if nick == self.bot.nick:
            self.log.info("%s left %s by %s", nick, channel, kwargs["event"])
            for (n, user) in self.active_users.copy().items():
                user.part(channel)
                if not user.still_in_channels():
                    del self.active_users[n]
            # Remove channel from administration
            self.channels.remove(channel)

        if nick not in self.active_users:
            return

        self.active_users[nick].part(channel)
        if not self.active_users[nick].still_in_channels():
            self.log.debug("Lost %s out of sight", mask.nick)
            del self.active_users[nick]

    @irc3.event(irc3.rfc.RPL_WHOREPLY)
    def on_who(
        self, channel=None, nick=None, username=None, host=None, server=None, **kwargs
    ):
        """Process a WHO reply since it could contain new information.

        Should only be processed for channels we are currently in!
        """
        if channel not in self.channels:
            self.log.debug(
                "Got WHO for channel I'm not in: {chan}".format(chan=channel)
            )
            return

        self.log.debug("Got WHO for %s: %s (%s)", channel, nick, host)

        if nick not in self.active_users:
            mask = IrcString("{}!{}@{}".format(nick, username, host))
            self.active_users[nick] = self.create_user(mask, [channel])
        else:
            self.active_users[nick].join(channel)

    def create_user(self, mask, channels):
        """Return a User object"""
        if self.identifying_method == "mask":

            async def id_func():
                return mask.host

            return User(mask, channels, id_func, self.bot.db)
        if self.identifying_method == "nickserv":

            async def get_account():
                user = self.get_user(mask.nick)
                if hasattr(user, "account"):
                    return user.account
                result = await self.bot.async_cmds.whois(mask.nick)
                if result["success"] and "account" in result:
                    user.account = str(result["account"])
                    return user.account
                else:
                    return mask.host

            return User(mask, channels, get_account, self.bot.db)
        if self.identifying_method == "whatcd":

            async def id_func():
                match = re.match(r"^\d+@(.*)\.\w+\.what\.cd", mask.host.lower())
                if match:
                    return match.group(1)
                else:
                    self.log.debug(
                        "Failed to extract what.cd user name"
                        "from {mask}".format(mask=mask)
                    )
                    return mask.host

            return User(mask, channels, id_func, self.bot.db)
        else:  # pragma: no cover
            raise ValueError("A valid identifying method should be configured")

    @classmethod
    def reload(cls, old):  # pragma: no cover
        users = old.active_users
        newinstance = cls(old.bot)
        for user in users.values():
            user.database = newinstance.bot.db
        newinstance.channels = old.channels
        newinstance.users = users
