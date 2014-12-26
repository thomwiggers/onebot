#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_onebot
----------------------------------

Tests for `onebot` module.
"""
from __future__ import unicode_literals

import pytest
import unittest

from irc3.testing import BotTestCase, patch, MagicMock
from irc3.utils import IrcString

from onebot.plugins.users import User


class UsersPluginTest(BotTestCase):

    config = {
        'includes': ['onebot.plugins.users'],
        'cmd': '!',
    }

    @patch('pymongo.MongoClient')
    def setUp(self, mock):
        self.callFTU()
        self.users = self.bot.get_plugin('onebot.plugins.users.UsersPlugin')

    def test_join(self):
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        user = self.bot.get_user('bar')
        assert user.nick == 'bar'
        assert user.host == 'foo@host'
        assert user.mask.host == 'foo@host'
        assert user.mask.nick == 'bar'
        assert user.channels == set(('#chan',))
        self.bot.dispatch(':bar!foo@host JOIN #chan2')
        assert user.channels == set(('#chan', '#chan2'))

    def test_join_part_kick(self):
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        assert '#chan' in self.users.channels
        self.bot.dispatch(':bar!foo@host JOIN #chan2')
        assert self.bot.get_user('bar').channels == set(('#chan', '#chan2'))
        self.bot.dispatch(':bar!foo@host PART #chan')
        assert self.bot.get_user('bar').channels == set(('#chan2',))
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        self.bot.dispatch(':adm!in@other KICK #chan bar')
        assert self.bot.get_user('bar').channels == set(('#chan2',))
        self.bot.dispatch(':bar!foo@host PART #chan2')
        with pytest.raises(KeyError):
            self.bot.get_user('bar')

        # make sure unknowns don't break things
        self.bot.dispatch(':anon!dont@know PART #chan')

    def test_bot_part(self):
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        self.bot.dispatch(':{}!foo@bar PART #chan'.format(self.bot.nick))
        with pytest.raises(KeyError):
            self.bot.get_user('bar')

    def test_nick_change(self):
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        self.bot.dispatch(':bar!foo@host NICK bar2')
        user = self.bot.get_user('bar2')
        assert user.nick == 'bar2'
        assert user.host == 'foo@host'
        # test other user gone
        with pytest.raises(KeyError):
            self.bot.get_user('bar')

        # Make sure we don't need to know the person
        self.bot.dispatch(':anonymous!dont@know NICK anon')

    def test_quit(self):
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        self.bot.dispatch(':bar!foo@host QUIT :quitmessage')
        with pytest.raises(KeyError):
            self.bot.get_user('bar')

        self.bot.dispatch(':bar!foo@host JOIN #chan')
        msg = ':{}!foo@bar QUIT :quitmsg'.format(self.bot.nick)
        self.bot.dispatch(msg)
        with pytest.raises(KeyError):
            self.bot.get_user('bar')
        assert self.users.channels == set()

    def test_who(self):
        # Only accept these if we're in that channel
        self.bot.dispatch(':server 352 irc3 #chan ~user host serv bar H@ :hoi')
        assert len(self.users.active_users) == 0

        self.users.channels.add('#chan')
        self.bot.dispatch(':server 352 irc3 #chan ~user host serv bar H@ :hoi')
        user = self.bot.get_user('bar')
        assert user.nick == 'bar'
        assert user.host == '~user@serv'
        assert user.channels == set(('#chan',))

        # Test adding chans to existing users
        self.users.channels.add('#chn2')
        self.bot.dispatch(':server 352 irc3 #chn2 ~user host serv bar H@ :hoi')
        assert '#chn2' in user.channels


class UserObjectTest(unittest.TestCase):

    def setUp(self):
        mask = IrcString('nick!user@host')
        self.user = User(mask, ['#foo'], mask.host)

    def test_user_needs_channels(self):
        with self.assertRaises(ValueError):
            User(IrcString('nick!user@host'), None, 'id')
        with self.assertRaises(ValueError):
            User(IrcString('nick!user@host'), '#chan', 'id')

    def test_init(self):
        assert self.user.nick == 'nick'
        assert self.user.host == 'user@host'
        assert self.user.mask == IrcString('nick!user@host')
        assert self.user.getid() == 'user@host'

    def test_equal(self):
        u = User(IrcString('nick!otheruser@otherhost'), ['#bar'], 'otherid')
        assert u == self.user

    def test_still_in_channels(self):
        assert self.user.still_in_channels()
        self.user.part('#foo')
        assert not self.user.still_in_channels()

    def test_join_part(self):
        self.user.channels = set(['#foo'])
        self.user.join('#foo')
        assert self.user.channels == set(['#foo'])
        self.user.join('#bar')
        assert self.user.channels == set(['#foo', '#bar'])
        self.user.part('#foo')
        assert self.user.channels == set(['#bar'])
        self.user.part('#bar')
        assert self.user.channels == set()

    @patch('onebot.plugins.database.DatabasePlugin.get_database')
    def test_get_settings(self, mock):
        mock.users = MagicMock()
        mock.users.find_one.return_value = {'setting': 'hi'}
        self.user.database = mock
        assert self.user.get_settings() == {'setting': 'hi'}
        assert self.user.get_setting('foo') is None
        assert self.user.get_setting('foo', 'default') == 'default'
        assert self.user.get_setting('setting') == 'hi'
        assert self.user.get_setting('setting', 'default') == 'hi'
        mock.users.find_one.return_value = None
        assert self.user.get_setting('foo', 'default') == 'default'


if __name__ == '__main__':
    unittest.main()
