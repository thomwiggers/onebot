#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_karma
----------------------------------

Tests for Karma module.
"""

from irc3.testing import BotTestCase, patch

from .test_plugin_users import MockDb
from onebot.plugins.karma import _format_key


class KarmaTestCase(BotTestCase):

    config = {
        'cmd': '!',
        'includes': [
            'onebot.plugins.karma',
        ],
    }

    @patch('irc3.plugins.storage.Storage')
    def setUp(self, mock):
        super(KarmaTestCase, self).setUp()
        self.callFTU()
        self.bot.db = MockDb()
        self.bot.dispatch(':bar!foo@host JOIN #chan')

    def assertSent(self, lines):
        """Assert that these lines have been sent"""
        self.assertEqual(self.bot.sent, lines)

    def test_increment(self):
        self.bot.dispatch(':root@localhost PRIVMSG #chan :foo bar++ baz')
        self.assertEquals(self.bot.db[_format_key('bar')]['up'], 1)
        self.assertEquals(self.bot.db[_format_key('bar')]['down'], 0)

    def test_increment_brackets(self):
        self.bot.dispatch(':root@localhost PRIVMSG #chan :(foo bar)++ baz')
        self.assertEquals(self.bot.db[_format_key('foo bar')]['up'], 1)
        self.assertEquals(self.bot.db[_format_key('foo bar')]['down'], 0)
        with self.assertRaises(KeyError):
            self.bot.db[_format_key('bar')]

    def test_decrement(self):
        self.bot.dispatch(':root@localhost PRIVMSG #chan :foo bar-- baz')
        self.assertEquals(self.bot.db[_format_key('bar')]['up'], 0)
        self.assertEquals(self.bot.db[_format_key('bar')]['down'], 1)

    def test_decrement_brackets(self):
        self.bot.dispatch(':root@localhost PRIVMSG #chan :(foo bar)-- baz')
        self.assertEquals(self.bot.db[_format_key('foo bar')]['up'], 0)
        self.assertEquals(self.bot.db[_format_key('foo bar')]['down'], 1)
        with self.assertRaises(KeyError):
            self.bot.db[_format_key('bar')]

    def test_unopened_bracket(self):
        self.bot.dispatch(':root@localhost PRIVMSG #chan :foo bar)-- baz')
        self.assertEquals(self.bot.db[_format_key('bar)')]['down'], 1)
        with self.assertRaises(KeyError):
            self.bot.db[_format_key('foo bar')]

    def test_unclosed_bracket(self):
        self.bot.dispatch(':root@localhost PRIVMSG #chan :(foo bar-- baz')
        self.assertEquals(self.bot.db[_format_key('bar')]['down'], 1)
        with self.assertRaises(KeyError):
            self.bot.db[_format_key('foo bar')]

    def test_karma_command(self):
        self.bot.dispatch(':root@localhost PRIVMSG #chan :foo bar++ baz')
        self.bot.dispatch(':root@localhost PRIVMSG #chan :foo bar++ baz')
        self.bot.dispatch(':root@localhost PRIVMSG #chan :(foo bar)++ baz')
        self.bot.dispatch(':root@localhost PRIVMSG #chan :foo bar-- baz')
        self.assertEquals(self.bot.db[_format_key('bar')]['up'], 2)
        self.assertEquals(self.bot.db[_format_key('bar')]['down'], 1)
        self.bot.dispatch(':root@localhost PRIVMSG #chan :!karma bar')
        self.assertSent(["PRIVMSG #chan :'bar' has a karma of 1 (2, 1)"])
        self.bot.dispatch(':root@localhost PRIVMSG #chan :!karma foo')
        self.assertSent(["PRIVMSG #chan :No karma stored for 'foo'"])
        self.bot.dispatch(':root@localhost PRIVMSG #chan :!karma foo bar')
        self.assertSent(["PRIVMSG #chan :'foo bar' has a karma of 1 (1, 0)"])
