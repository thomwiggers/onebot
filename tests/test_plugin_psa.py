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
            ${hash}channel1
            '${hash}channel2
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
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!psa best bot')
        for channels in self.bot.channels:
            self.assertSent(['PRIVMSG {} :best bot'.format(channels)])
