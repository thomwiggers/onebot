#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_antispam
----------------------------------

Tests for antispam module.
"""
from irc3.testing import patch
from onebot.testing import BotTestCase

import asyncio

from .test_plugin_users import MockDb


async def empty():
    await asyncio.sleep(0.001)


class AntispamTestCase(BotTestCase):

    config = {"cmd": "!"}

    def assertSent(self, lines):
        """Assert that these lines have been sent"""
        self.assertEqual(self.bot.sent, lines)

    @patch("irc3.plugins.storage.Storage")
    def setUp(self, mock):
        super(AntispamTestCase, self).setUp()
        self.config["loop"] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config["loop"])
        self.callFTU()
        self.bot.include("onebot.plugins.antispam")
        self.bot.db = MockDb()

        # join some users
        self.bot.dispatch(":a!the@boss JOIN #chan")
        self.bot.dispatch(":b!the@boss JOIN #chan")
        self.bot.dispatch(":c!the@boss JOIN #chan")
        self.bot.dispatch(":d!the@boss JOIN #chan")
        self.bot.dispatch(":e!the@boss JOIN #chan")
        self.bot.dispatch(":f!the@boss JOIN #chan")

    def tearDown(self):
        super().tearDown()
        self.bot.SIGINT()

    def test_spam_nicks(self):
        self.bot.dispatch(":a!the@boss PRIVMSG #chan :hi everyone")
        self.bot.dispatch(":a!the@boss PRIVMSG #chan :hi abcdef")
        self.bot.dispatch(":a!the@boss PRIVMSG #chan :a b c d e f")
        self.bot.loop.run_until_complete(empty())
        self.assertSent(["KICK #chan a :Don't excessively highlight people."])

    def test_repeat_spam(self):
        async def wrap():
            self.bot.dispatch(":a!the@boss PRIVMSG #chan :blurp")
            await asyncio.sleep(0.001)

        self.bot.loop.run_until_complete(wrap())
        self.bot.loop.run_until_complete(wrap())
        self.bot.loop.run_until_complete(wrap())
        self.bot.loop.run_until_complete(wrap())
        self.assertSent([])
        self.bot.loop.run_until_complete(wrap())
        self.assertSent(
            [
                "KICK #chan a :Try to come up with something more "
                "creative. (5 repeating lines)"
            ]
        )
