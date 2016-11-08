#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_plugin_psa
----------------------------------

Tests for PSA module
"""

from irc3.testing import ini2config, BotTestCase, patch

from .test_plugin_users import MockDb


class PSATestCase(BotTestCase):

    config = {
        'include': [
            'onebot.lugins.psa',
            'irc3.plugins.command'
        ],
        'autojoins': [
            '${hash}chan1',
            '${hash}chan2'
        ]
        'irc3.plugins.command': {
            'guard': 'onebot.plugins.acl.user_based_policy'
        }
    }

    @patch('irc3.plugins.storage.Storage')
    def setUp(self, mock):
        super(PSATestCase, self).setUp()
        self.callFTU()
        self.bot.db = MockDb({
            'wat@bro': {'permissions': {'all_permissions'}}
        })

    def test_psa(self):
        self.bot.dispatch(':im!wat@bro PRIVMSG #chan1 :!psa foo')
        self.assertSent(['PRIVMSG #chan1 :foo'])
        self.assertSent(['PRIVMSG #chan2 :foo'])
