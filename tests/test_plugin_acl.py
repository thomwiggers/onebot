#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_acl
----------------------------------

Tests for ACL module.
"""

import asyncio

from irc3.testing import patch
from irc3.plugins.command import command

from onebot.testing import BotTestCase

from .test_plugin_users import MockDb


@command(permission="test")
def cmd(bot, mask, target, args, **kwargs):
    """Test Command

    %%cmd
    """
    bot.privmsg(target, "Done")


@command
async def cmd2(bot, mask, target, args, **kwargs):
    """Another test command

    %%cmd2
    """
    bot.privmsg(target, "Done")


class WhoamiTestCase(BotTestCase):
    """Test the whoami command with a realistic config"""

    config = {
        "includes": ["onebot.plugins.acl"],
        "cmd": ".",
        "irc3.plugins.command": {"guard": "onebot.plugins.acl.user_based_policy"},
        "onebot.plugins.users": {"identify_by": "mask"},
    }

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        super().setUp()
        self.config["loop"] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config["loop"])
        self.callFTU()
        self.bot.db = MockDb()

    def tearDown(self):
        super().tearDown()
        self.bot.SIGINT()

    def test_whoami_is_registered(self):
        commands = self.bot.get_plugin("irc3.plugins.command.Commands")
        assert "whoami" in commands

    def test_whoami_without_permissions(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :.whoami")
        self.bot.loop.run_until_complete(asyncio.sleep(0.01))
        # the identity itself never hits the channel
        assert self.bot.sent == [
            "PRIVMSG bar :You are foo@host without any permissions",
            "PRIVMSG #chan :I've sent you a PRIVMSG",
        ]

    def test_whoami_with_permissions(self):
        self.bot.db["foo@host"] = {"permissions": '["admin", "view"]'}
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :.whoami")
        self.bot.loop.run_until_complete(asyncio.sleep(0.01))
        assert self.bot.sent == [
            "PRIVMSG bar :You are foo@host with permissions: admin, view",
            "PRIVMSG #chan :I've sent you a PRIVMSG",
        ]

    def test_whoami_in_query(self):
        self.bot.dispatch(":bar!foo@host JOIN #chan")
        self.bot.dispatch(":bar!foo@host PRIVMSG {} :.whoami".format(self.bot.nick))
        self.bot.loop.run_until_complete(asyncio.sleep(0.01))
        assert self.bot.sent == [
            "PRIVMSG bar :You are foo@host without any permissions"
        ]

    def test_whoami_unknown_user(self):
        # we're not in #chan, so we never saw this user
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :.whoami")
        self.bot.loop.run_until_complete(asyncio.sleep(0.01))
        assert self.bot.sent == ["PRIVMSG #chan :I have no idea who you are."]


class UserBasedGuardPolicyTestCase(BotTestCase):
    config = {
        "includes": ["irc3.plugins.command", __name__],
        "irc3.plugins.command": {"guard": "onebot.plugins.acl.user_based_policy"},
    }

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        super().setUp()
        self.config["loop"] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config["loop"])
        self.callFTU()
        self.bot.db = MockDb()

    def tearDown(self):
        super().tearDown()
        self.bot.SIGINT()

    def test_command_allowed(self):
        async def wrap():
            self.bot.dispatch(":im!the@boss JOIN #chan")
            self.bot.db["the@boss"] = {"permissions": '["test"]'}
            self.bot.dispatch(":im!the@boss PRIVMSG #chan :!cmd")
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertSent(["PRIVMSG #chan :Done"])

    def test_command_not_allowed(self):
        async def wrap():
            self.bot.dispatch(":nobody!idont@knowu PRIVMSG #chan :!cmd")
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertSent(["PRIVMSG nobody :You are not allowed to use the cmd command"])

    def test_command_ignored(self):
        async def wrap():
            self.bot.dispatch(":Groxxxy!stupid@idiot JOIN #chan")
            self.bot.db["stupid@idiot"] = {"permissions": '["ignore"]'}
            self.bot.dispatch(":Groxxxy!stupid@idiot PRIVMSG #chan :!cmd2")
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertSent(
            ["PRIVMSG Groxxxy :You are not allowed to use the cmd2 command"]
        )

    def assertSent(self, lines):
        """Assert that these lines have been sent"""
        self.assertEqual(self.bot.sent, lines)


class SuperAdminTestCase(BotTestCase):
    """Test that the superadmin config value grants all_permissions via the guard."""

    config = {
        "cmd": "!",
        "irc3.plugins.command": {"guard": "onebot.plugins.acl.user_based_policy"},
        "onebot.plugins.acl": {"superadmin": "root@localhost"},
    }

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        super().setUp()
        self.config["loop"] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config["loop"])
        self.callFTU()
        self.bot.db = MockDb()
        self.bot.include("onebot.plugins.acl")
        self.bot.dispatch(":bar!foo@host JOIN #chan")

    def tearDown(self):
        super().tearDown()
        self.bot.SIGINT()

    def assertSent(self, lines):
        self.assertEqual(self.bot.sent, lines)

    def test_superadmin_can_use_acl(self):
        async def wrap():
            self.bot.dispatch(":superadmin!root@localhost JOIN #chan")
            self.bot.dispatch(
                ":superadmin!root@localhost PRIVMSG #chan :!acl add bar admin"
            )
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertEqual(self.bot.db["foo@host"].get("permissions"), '["admin"]')
        self.assertSent(["PRIVMSG #chan :Updated permissions for bar"])

    def test_regular_user_cannot_use_acl(self):
        async def wrap():
            self.bot.dispatch(":regular!user@somehost JOIN #chan")
            self.bot.dispatch(
                ":regular!user@somehost PRIVMSG #chan :!acl add bar admin"
            )
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertSent(["PRIVMSG regular :You are not allowed to use the acl command"])


class ACLTestCase(BotTestCase):
    config = {"cmd": "!", "onebot.plugins.acl": {"superadmin": "root@localhost"}}

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        super().setUp()
        self.config["loop"] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config["loop"])
        self.callFTU()
        self.bot.db = MockDb()
        self.bot.include("onebot.plugins.acl")
        self.bot.dispatch(":bar!foo@host JOIN #chan")

    def tearDown(self):
        super().tearDown()
        self.bot.SIGINT()

    def assertSent(self, lines):
        """Assert that these lines have been sent"""
        self.assertEqual(self.bot.sent, lines)

    def test_add_acl(self):
        async def wrap():
            self.bot.dispatch(":root@localhost PRIVMSG #chan :!acl add bar admin")
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertEqual(self.bot.db["foo@host"].get("permissions"), '["admin"]')
        self.assertSent(["PRIVMSG #chan :Updated permissions for bar"])

    def test_add_unknown_user(self):
        async def wrap():
            self.bot.dispatch(":root@localhost PRIVMSG #chan :!acl add bat admin")
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertEqual(self.bot.db.get("bat", {}).get("permissions", []), [])
        self.assertSent(["PRIVMSG #chan :I don't know bat. Please use --by-id"])

    def test_add_acl_id(self):
        async def wrap():
            self.bot.dispatch(
                ":root@localhost PRIVMSG #chan :!acl add --by-id bak admin"
            )
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertEqual(self.bot.db["bak"].get("permissions"), '["admin"]')
        self.assertSent(["PRIVMSG #chan :Updated permissions for bak"])

    def test_invalid_permission(self):
        async def wrap():
            self.bot.dispatch(":root@localhost PRIVMSG #chan :!acl add bat fietsen")
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertEqual(self.bot.db.get("bat", {}).get("permissions", []), [])
        self.assertSent(
            [
                "PRIVMSG #chan :Invalid permission level. Available permissions: "
                "operator, admin, wiki, view, ignore"
            ]
        )

    def test_remove_acl(self):
        self.bot.db["foo@host"] = {"permissions": '["admin"]'}

        # sanity check
        self.assertEqual(self.bot.db["foo@host"].get("permissions"), '["admin"]')

        async def wrap():
            self.bot.dispatch(":root@localhost PRIVMSG #chan :!acl remove bar admin")
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.assertEqual(self.bot.db["foo@host"].get("permissions"), "[]")
