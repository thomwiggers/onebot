#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_onebot
----------------------------------

Tests for `onebot` module.
"""

from __future__ import unicode_literals

import asyncio
import unittest

from irc3.testing import patch
from irc3.utils import IrcString
from onebot.testing import BotTestCase

from onebot.plugins.users import User


class MockDb(dict):
    def set(self, k, **kwargs):
        if not self.get(k):
            self[k] = kwargs
        else:
            self[k].update(**kwargs)


class UsersPluginTestWithNickserv(BotTestCase):
    """Test the NickServ identifying method"""

    config = {
        "includes": ["onebot.plugins.users"],
        "cmd": "!",
        "onebot.plugins.users": {"identify_by": "nickserv"},
    }

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        self.config["loop"] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config["loop"])
        self.callFTU()
        self.bot.db = MockDb()
        self.users = self.bot.get_plugin("onebot.plugins.users.UsersPlugin")

    def tearDown(self):
        super().tearDown()
        self.bot.SIGINT()

    def test_join(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.loop.run_until_complete(asyncio.sleep(0.001))
        user = self.bot.get_user("bar")
        assert user, "User should exist!"
        task = asyncio.ensure_future(user.id())
        self.bot.loop.run_until_complete(asyncio.sleep(0.001))

        self.bot.dispatch(":localhost 311 me bar foo host * :realname")
        self.bot.dispatch(":localhost 330 me bar nsaccount :is logged in as")
        self.bot.dispatch(":localhost 318 me bar :End")

        self.bot.loop.run_until_complete(task)
        assert task.result() == "nsaccount"

        # subsequent gets should not need another whois
        task = asyncio.ensure_future(user.id())
        self.bot.loop.run_until_complete(task)
        assert task.result() == "nsaccount"

    def test_identify_user_known_only_from_query(self):
        """Users that only ever PM the bot should still be identifiable"""
        self.bot.dispatch(":bar!foo@host PRIVMSG {} :hi".format(self.bot.nick))
        self.bot.loop.run_until_complete(asyncio.sleep(0.001))
        user = self.bot.get_user("bar")
        assert user, "User should exist!"
        task = asyncio.ensure_future(user.id())
        self.bot.loop.run_until_complete(asyncio.sleep(0.001))

        self.bot.dispatch(":localhost 311 me bar foo host * :realname")
        self.bot.dispatch(":localhost 330 me bar nsaccount :is logged in as")
        self.bot.dispatch(":localhost 318 me bar :End")

        self.bot.loop.run_until_complete(task)
        assert task.result() == "nsaccount"


class UsersPluginTestWithWhatcd(BotTestCase):
    """Test the What.CD identifying method"""

    config = {
        "includes": ["onebot.plugins.users"],
        "cmd": "!",
        "onebot.plugins.users": {"identify_by": "whatcd"},
    }

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        self.config["loop"] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config["loop"])
        self.callFTU()
        self.bot.db = MockDb()
        self.users = self.bot.get_plugin("onebot.plugins.users.UsersPlugin")

    def tearDown(self):
        super().tearDown()
        self.bot.SIGINT()

    def test_join(self):
        self.bot.dispatch(":bar!200779@nankers.member.what.cd JOIN #chan")
        self.bot.loop.run_until_complete(asyncio.sleep(0.001))
        user = self.bot.get_user("bar")
        assert user
        task = asyncio.ensure_future(user.id())
        self.bot.loop.run_until_complete(task)
        assert task.result() == "nankers"


class UsersPluginTest(BotTestCase):
    config = {
        "includes": ["onebot.plugins.users"],
        "cmd": "!",
    }

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        self.callFTU()
        self.bot.db = MockDb()
        self.users = self.bot.get_plugin("onebot.plugins.users.UsersPlugin")

    def test_join(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        user = self.bot.get_user("bar")
        assert user.nick == "bar"
        assert user.host == "foo@host"
        assert user.mask.host == "foo@host"
        assert user.mask.nick == "bar"
        assert user.channels == set(("#chan",))
        self.bot.dispatch(":bar!foo@host JOIN #chan2")
        assert user.channels == set(("#chan", "#chan2"))

    def test_join_part_kick(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        assert "#chan" in self.users.channels
        self.bot.dispatch(":bar!foo@host JOIN #chan2")
        assert self.bot.get_user("bar").channels == set(("#chan", "#chan2"))
        self.bot.dispatch(":bar!foo@host PART #chan")
        assert self.bot.get_user("bar").channels == set(("#chan2",))
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":adm!in@other KICK #chan bar")
        assert self.bot.get_user("bar").channels == set(("#chan2",))
        self.bot.dispatch(":bar!foo@host PART #chan2")
        assert self.bot.get_user("bar") is None

        # make sure unknowns don't break things
        self.bot.dispatch(":anon!dont@know PART #chan")

    def test_bot_part(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":bar2!foo@host JOIN #chan")
        self.bot.dispatch(":bar3!foo@host JOIN #chan")
        self.bot.dispatch(":{}!foo@bar PART #chan".format(self.bot.nick))
        assert self.bot.get_user("bar") is None
        assert self.bot.get_user("bar2") is None
        assert self.bot.get_user("bar3") is None

    def test_nick_change(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":bar!foo@host NICK bar2")
        user = self.bot.get_user("bar2")
        assert user.nick == "bar2"
        assert user.host == "foo@host"
        # test other user gone
        assert self.bot.get_user("bar") is None

        # Make sure we don't need to know the person
        self.bot.dispatch(":anonymous!dont@know NICK anon")

    def test_quit(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":bar!foo@host QUIT :quitmessage")
        assert self.bot.get_user("bar") is None

        self.bot.dispatch(":bar!foo@host JOIN #chan")
        msg = ":{}!foo@bar QUIT :quitmsg".format(self.bot.nick)
        self.bot.dispatch(msg)
        assert self.bot.get_user("bar") is None
        assert self.users.channels == set()

    def test_names(self):
        self.users.channels.add("#chan")
        self.bot.dispatch(":server 353 me = #chan :bar bar2 bar3")
        self.bot.dispatch(":server 366 me #chan :End")
        # we only add users we know masks for
        assert len(self.users.active_users) == 0

    def test_who(self):
        # Only accept these if we're in that channel
        self.bot.dispatch(":server 352 irc3 #chan ~user host serv bar H@ :hoi")
        assert len(self.users.active_users) == 0

        self.users.channels.add("#chan")
        self.bot.dispatch(":server 352 irc3 #chan ~user host serv bar H@ :hoi")
        user = self.bot.get_user("bar")
        assert user.nick == "bar"
        assert user.host == "~user@host"
        assert user.channels == set(("#chan",))

        # Test adding chans to existing users
        self.users.channels.add("#chn2")
        self.bot.dispatch(":server 352 irc3 #chn2 ~user host serv bar H@ :hoi")
        assert "#chn2" in user.channels

    def test_privmsg(self):
        # Only accept these if we're in that channel
        self.bot.dispatch(":foo!bar@baz PRIVMSG #chan :hi")
        self.bot.dispatch(":foo2!ba2@baz NOTICE #chan :hi")
        assert self.bot.get_user("foo") is None
        assert self.bot.get_user("foo2") is None
        assert len(self.users.active_users) == 0

        self.users.channels.add("#chan")
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :hi!")
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :hi!")
        user = self.bot.get_user("bar")
        assert user.nick == "bar"
        assert user.host == "foo@host"
        assert user.channels == set(("#chan",))
        self.users.channels.add("#chan2")
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan2 :hi!")
        assert user.channels == set(("#chan", "#chan2"))

    def test_privmsg_in_query(self):
        self.bot.dispatch(":bar!foo@host PRIVMSG {} :hi!".format(self.bot.nick))
        user = self.bot.get_user("bar")
        assert user is not None
        assert user.nick == "bar"
        assert user.host == "foo@host"
        assert user.channels == set()

        # a query doesn't make us forget channels, and parting a channel the
        # user was never seen in doesn't drop them either
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        assert user.channels == set(("#chan",))
        self.bot.dispatch(":bar!foo@host PRIVMSG {} :hi!".format(self.bot.nick))
        assert user.channels == set(("#chan",))

    def test_query_notice_is_ignored(self):
        # services talk to us in NOTICEs; they're not users
        self.bot.dispatch(
            ":NickServ!NickServ@services. NOTICE {} :You are now identified".format(
                self.bot.nick
            )
        )
        assert self.bot.get_user("NickServ") is None
        assert len(self.users.active_users) == 0

    def test_bot_part_keeps_users_from_other_channels(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":bar2!foo@host JOIN #chan2")
        self.bot.dispatch(":{}!foo@bar PART #chan".format(self.bot.nick))
        assert self.bot.get_user("bar") is None
        assert self.bot.get_user("bar2") is not None

    def test_who_on_join(self):
        self.bot.dispatch(":{}!bar@baz JOIN #chan2".format(self.bot.nick))
        self.assertSent(["WHO #chan2"])

    def test_redact_nicks(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":baz!foo@host JOIN #chan")

        # redact all
        msg = "Hello bar and baz"
        redacted = self.bot.redact_nicks(msg)
        assert redacted == "Hello b·ar and b·az"

        # redact for specific channel
        msg = "Hello bar and baz"
        redacted = self.bot.redact_nicks(msg, target="#chan")
        assert redacted == "Hello b·ar and b·az"

        # redact for other channel (should be no-op for these nicks)
        redacted = self.bot.redact_nicks(msg, target="#other")
        assert redacted == msg

        # test nick with special chars
        self.bot.dispatch(":[baz]!foo@host JOIN #chan")
        msg = "Hello [baz]"
        redacted = self.bot.redact_nicks(msg, target="#chan")
        assert redacted == "Hello [·baz]"

        # Method itself DOES redact if it's at the start
        msg = "baz: hello"
        redacted = self.bot.redact_nicks(msg, target="#chan")
        assert redacted == "b·az: hello"


class UsersPluginWhoamiTest(BotTestCase):
    """Test the whoami command, which needs a real event loop"""

    config = {
        "includes": ["onebot.plugins.users"],
        "cmd": "!",
    }

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        self.config["loop"] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config["loop"])
        self.callFTU()
        self.bot.db = MockDb()
        self.users = self.bot.get_plugin("onebot.plugins.users.UsersPlugin")

    def tearDown(self):
        super().tearDown()
        self.bot.SIGINT()

    def test_whoami(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :!whoami")
        self.bot.loop.run_until_complete(asyncio.sleep(0.01))
        assert self.bot.sent == ["PRIVMSG #chan :You are foo@host (bar!foo@host)"]

    def test_whoami_in_query(self):
        nick = self.bot.nick
        self.bot.dispatch(":bar!foo@host PRIVMSG {} :!whoami".format(nick))
        self.bot.loop.run_until_complete(asyncio.sleep(0.01))
        assert self.bot.sent == ["PRIVMSG bar :You are foo@host (bar!foo@host)"]

    def test_whoami_unknown_user(self):
        # we're not in #chan, so we never saw this user
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :!whoami")
        self.bot.loop.run_until_complete(asyncio.sleep(0.01))
        assert self.bot.get_user("bar") is None
        assert self.bot.sent == ["PRIVMSG #chan :I have no idea who you are."]


class UserObjectTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        mask = IrcString("nick!user@host")

        async def id_func():
            return mask

        self.user = User(mask, ["#foo"], id_func, MockDb())

    def tearDown(self):
        super().tearDown()

    def test_user_needs_channels(self):
        with self.assertRaises(ValueError):
            User(IrcString("nick!user@host"), None, lambda x: "id")
        with self.assertRaises(ValueError):
            User(IrcString("nick!user@host"), "#chan", lambda x: "id")

    def test_init(self):
        assert self.user.nick == "nick"
        assert self.user.host == "user@host"
        assert self.user.mask == IrcString("nick!user@host")

    def test_equal(self):
        u = User(IrcString("nick!otheruser@otherhost"), ["#bar"], lambda x: "otherid")
        assert u == self.user

    def test_still_in_channels(self):
        assert self.user.still_in_channels()
        self.user.part("#foo")
        assert not self.user.still_in_channels()

    def test_join_part(self):
        self.user.channels = set(["#foo"])
        self.user.join("#foo")
        assert self.user.channels == set(["#foo"])
        self.user.join("#bar")
        assert self.user.channels == set(["#foo", "#bar"])
        self.user.part("#foo")
        assert self.user.channels == set(["#bar"])
        self.user.part("#bar")
        assert self.user.channels == set()

    async def test_get_settings(self):
        await self.user.set_settings({"setting": "hi"})
        assert (await self.user.get_settings()) == {"setting": "hi"}
        assert (await self.user.get_setting("foo")) is None
        assert (await self.user.get_setting("foo", "default")) == "default"
        assert (await self.user.get_setting("setting")) == "hi"
        assert (await self.user.get_setting("setting", "default")) == "hi"
        assert (await self.user.get_setting("foo", "default")) == "default"
        await self.user.set_setting("setting", "bar")
        assert (await self.user.get_setting("setting")) == "bar"


if __name__ == "__main__":
    unittest.main()
