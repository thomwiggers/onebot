#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_onebot
----------------------------------

Tests for `onebot` module.
"""
from __future__ import unicode_literals

import asyncio
import unittest

from irc3.testing import BotTestCase, patch
from irc3.utils import IrcString

from onebot.plugins.users import User


class UsersPluginTest(BotTestCase):

    config = {
        'includes': ['onebot.plugins.users'],
        'cmd': '!',
    }

    @patch('irc3.plugins.storage.Storage')
    def setUp(self, mock):
        self.callFTU()
        self.bot.db = dict()
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
        assert self.bot.get_user('bar') is None

        # make sure unknowns don't break things
        self.bot.dispatch(':anon!dont@know PART #chan')

    def test_bot_part(self):
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        self.bot.dispatch(':bar2!foo@host JOIN #chan')
        self.bot.dispatch(':bar3!foo@host JOIN #chan')
        self.bot.dispatch(':{}!foo@bar PART #chan'.format(self.bot.nick))
        assert self.bot.get_user('bar') is None
        assert self.bot.get_user('bar2') is None
        assert self.bot.get_user('bar3') is None

    def test_nick_change(self):
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        self.bot.dispatch(':bar!foo@host NICK bar2')
        user = self.bot.get_user('bar2')
        assert user.nick == 'bar2'
        assert user.host == 'foo@host'
        # test other user gone
        assert self.bot.get_user('bar') is None

        # Make sure we don't need to know the person
        self.bot.dispatch(':anonymous!dont@know NICK anon')

    def test_quit(self):
        self.bot.dispatch(':bar!foo@host JOIN #chan')
        self.bot.dispatch(':bar!foo@host QUIT :quitmessage')
        assert self.bot.get_user('bar') is None

        self.bot.dispatch(':bar!foo@host JOIN #chan')
        msg = ':{}!foo@bar QUIT :quitmsg'.format(self.bot.nick)
        self.bot.dispatch(msg)
        assert self.bot.get_user('bar') is None
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

    def test_privmsg(self):
        # Only accept these if we're in that channel
        self.bot.dispatch(':foo!bar@baz PRIVMSG #chan :hi')
        self.bot.dispatch(':foo2!ba2@baz NOTICE #chan :hi')
        assert self.bot.get_user('foo') is None
        assert self.bot.get_user('foo2') is None
        assert len(self.users.active_users) == 0

        self.users.channels.add('#chan')
        self.bot.dispatch(':bar!foo@host PRIVMSG #chan :hi!')
        self.bot.dispatch(':bar!foo@host PRIVMSG #chan :hi!')
        user = self.bot.get_user('bar')
        assert user.nick == 'bar'
        assert user.host == 'foo@host'
        assert user.channels == set(('#chan',))
        self.users.channels.add('#chan2')
        self.bot.dispatch(':bar!foo@host PRIVMSG #chan2 :hi!')
        assert user.channels == set(('#chan', '#chan2'))


class UserObjectTest(unittest.TestCase):

    def setUp(self):
        mask = IrcString('nick!user@host')

        @asyncio.coroutine
        def id_func(self):
            return mask

        self.user = User(mask, ['#foo'], id_func, dict())

    def test_user_needs_channels(self):
        with self.assertRaises(ValueError):
            User(IrcString('nick!user@host'), None, lambda x: 'id')
        with self.assertRaises(ValueError):
            User(IrcString('nick!user@host'), '#chan', lambda x: 'id')

    def test_init(self):
        assert self.user.nick == 'nick'
        assert self.user.host == 'user@host'
        assert self.user.mask == IrcString('nick!user@host')

    def test_equal(self):
        u = User(IrcString('nick!otheruser@otherhost'),
                 ['#bar'], lambda x: 'otherid')
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

    def test_get_settings(self):

        @asyncio.coroutine
        def wrap():
            self.user.set_settings({'setting': 'hi'})
            yield from asyncio.sleep(0.01)
            assert (yield from self.user.get_settings()) == {'setting': 'hi'}
            assert (yield from self.user.get_setting('foo')) is None
            assert (yield from self.user.get_setting(
                'foo', 'default')) == 'default'
            assert (yield from self.user.get_setting('setting')) == 'hi'
            assert (yield from self.user.get_setting(
                'setting', 'default')) == 'hi'
            assert (yield from self.user.get_setting(
                'foo', 'default')) == 'default'
            self.user.set_setting('setting', 'bar')
            yield from asyncio.sleep(0.01)
            assert (yield from self.user.get_setting('setting')) == 'bar'
        asyncio.get_event_loop().run_until_complete(wrap())


if __name__ == '__main__':
    unittest.main()