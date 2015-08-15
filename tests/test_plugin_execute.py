#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_execute
----------------------------------

Tests for Execute plugin
"""

from irc3.testing import BotTestCase


class ExecutePluginTestCase(BotTestCase):

    config = {
        'includes': [
            'onebot.plugins.execute'
        ],
        'onebot.plugins.execute': {
            'commands': [
                'command1',
                'command2'
            ]
        }
    }

    def setUp(self):
        super(ExecutePluginTestCase, self).setUp()
        self.callFTU()
        self.bot.db = {}

    def test_command_allowed(self):
        self.bot.notify('connection_made')
        self.assertSent(['command1', 'command2'])
