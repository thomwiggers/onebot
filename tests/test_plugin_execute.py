#!/usr/bin/env python3

"""
test_onebot_execute
----------------------------------

Tests for Execute plugin
"""

from onebot.testing import BotTestCase


class ExecutePluginTestCase(BotTestCase):
    config = {
        "includes": ["onebot.plugins.execute"],
        "onebot.plugins.execute": {"commands": ["command1", "command2"]},
    }

    def setUp(self):
        super().setUp()
        self.callFTU()
        self.bot.db = {}

    def test_connection_made(self):
        self.bot.dispatch(":irc.server 376 foo!nick@bar :something")
        self.assertSent(["command1", "command2"])
