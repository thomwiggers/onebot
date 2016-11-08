#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_botui
----------------------------------

Tests for botui module.
"""
from irc3.testing import BotTestCase, patch

from .test_plugin_users import MockDb


class BotUITestCase(BotTestCase):

    config = {
        'includes': [
            'onebot.plugins.botui',
            'irc3.plugins.command'
        ],
        'cmd': '!'
    }

    @patch('irc3.plugins.storage.Storage')
    def setUp(self, mock):
        super(BotUITestCase, self).setUp()
        self.callFTU()
        self.bot.db = MockDb({
            'the@boss': {'permissions': {'all_permissions'}}
        })

    def test_invite(self):
        self.bot.dispatch(
            ':im!the@boss INVITE {}!the@bot #chan'.format(self.bot.nick))
        self.assertSent([
            'PRIVMSG im :Never accept an invitation from a stranger '
            'unless he gives you candy. -- Linda Festa'])
        self.bot.get_plugin('onebot.plugins.botui.BotUI')._autojoin = True
        self.bot.dispatch(
            ':im!the@boss INVITE {}!the@bot #chan'.format(self.bot.nick))
        self.assertSent(['JOIN #chan'])

    def test_join(self):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!join #chan2')
        self.assertSent(['JOIN #chan2'])
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!join #chan2 password')
        self.assertSent(['JOIN #chan2 password'])

    def test_part(self):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!part')
        self.assertSent(['PART #chan'])
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!part #chan2')
        self.assertSent(['PART #chan2'])

    def test_quit(self):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!quit')
        self.assertSent(['QUIT :-- im'])
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!quit various reasons')
        self.assertSent(['QUIT :various reasons -- im'])

    def test_nick(self):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!nick foobar')
        self.assertSent(['NICK foobar'])

    def test_mode(self):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!mode +B')
        self.assertSent(['MODE {} +B'.format(self.bot.nick)])

    def test_msg(self):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!msg #foo best bot')
        self.assertSent(['PRIVMSG #foo :best bot'])
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!msg foo best bot')
        self.assertSent(['PRIVMSG foo :best bot'])

    def test_quote(self):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!quote OPER foo')
        self.assertSent(['OPER foo'])

    @patch('sys.exit')
    def test_restart(self, mock):
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!restart')
        mock.assert_called_with(2)
        self.assertSent(['QUIT :-- im (restart)'])
        self.bot.dispatch(':im!the@boss PRIVMSG #chan :!restart with reason')
        mock.assert_called_with(2)
        self.assertSent(['QUIT :with reason -- im (restart)'])
