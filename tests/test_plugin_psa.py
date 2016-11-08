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

    config = ini2config("""
        [bot]
        includes=
            onebot.plugins.psa
            irc3.plugins.command

        autojoins=
            ${hash}chan1
            ${hash}chan2
        cmd= !
    """)

    @patch('irc3.plugins.storage.Storage')
    def setUp(self, mock):
        super(PSATestCase, self).setUp()
        self.callFTU()
        self.bot.db = MockDb({
            'the@boss': {'permissions': {'all_permissions'}}
        })

    def test_psa(self):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan1 :!psa best bot')
        self.assertSent(['PRIVMSG #chan1 :best bot'])
        self.assertSent(['PRIVMSG #chan2 :best bot'])
