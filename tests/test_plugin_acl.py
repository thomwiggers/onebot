#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_acl
----------------------------------

Tests for ACL module.
"""
import asyncio

from irc3.testing import BotTestCase, patch
from irc3.plugins.command import command

from .test_plugin_users import MockDb


@command(permission='test')
def cmd(bot, mask, target, args, **kwargs):
    """Test Command

        %%cmd
    """
    bot.privmsg(target, 'Done')


@command
def cmd2(bot, mask, target, args, **kwargs):
    """Another test command

        %%cmd2
    """
    bot.privmsg(target, 'Done')


class UserBasedGuardPolicyTestCase(BotTestCase):

    config = {
        'includes': [
            'irc3.plugins.command',
            __name__
        ],
        'irc3.plugins.command': {
            'guard': 'onebot.plugins.acl.user_based_policy'
        }
    }

    @patch('irc3.plugins.storage.Storage')
    def setUp(self, mock):
        super(UserBasedGuardPolicyTestCase, self).setUp()
        self.config['loop'] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config['loop'])
        self.callFTU()
        self.bot.db = MockDb()

    def test_command_allowed(self):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':im!the@boss JOIN #chan')
            self.bot.db['the@boss'] = {'permissions': {'test'}}
            self.bot.dispatch(':im!the@boss PRIVMSG #chan :!cmd')
            yield from asyncio.sleep(0.1)
        self.bot.loop.run_until_complete(wrap())
        self.assertSent(['PRIVMSG #chan :Done'])

    def test_command_not_allowed(self):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':nobody!idont@knowu PRIVMSG #chan :!cmd')
            yield from asyncio.sleep(0.1)
        self.bot.loop.run_until_complete(wrap())
        self.assertSent(
            ['PRIVMSG nobody :You are not allowed to use the cmd command'])

    def test_command_ignored(self):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':Groxxxy!stupid@idiot JOIN #chan')
            self.bot.db['stupid@idiot'] = {'permissions': {'ignore'}}
            self.bot.dispatch(':Groxxxy!stupid@idiot PRIVMSG #chan :!cmd2')
            yield from asyncio.sleep(0.1)

        self.bot.loop.run_until_complete(wrap())
        self.assertSent(
            ['PRIVMSG Groxxxy :You are not allowed to use the cmd2 command'])

    def assertSent(self, lines):
        """Assert that these lines have been sent"""
        self.assertEqual(self.bot.sent, lines)


class ACLTestCase(BotTestCase):

    config = {
        'cmd': '!',
        'onebot.plugins.acl': {
            'superadmin': 'root@localhost'
        }
    }

    @patch('irc3.plugins.storage.Storage')
    def setUp(self, mock):
        super(ACLTestCase, self).setUp()
        self.config['loop'] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config['loop'])
        self.callFTU()
        self.bot.db = MockDb()
        self.bot.include('onebot.plugins.acl')
        self.bot.dispatch(':bar!foo@host JOIN #chan')

    def assertSent(self, lines):
        """Assert that these lines have been sent"""
        self.assertEqual(self.bot.sent, lines)

    def test_add_acl(self):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(
                ':root@localhost PRIVMSG #chan :!acl add bar admin')
            yield from asyncio.sleep(0.1)
        self.bot.loop.run_until_complete(wrap())
        self.assertEquals(self.bot.db['foo@host'].get('permissions'),
                          ['admin'])
        self.assertSent(['PRIVMSG #chan :Updated permissions for bar'])

    def test_add_unknown_user(self):

        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(
                ':root@localhost PRIVMSG #chan :!acl add bat admin')
            yield from asyncio.sleep(0.1)
        self.bot.loop.run_until_complete(wrap())
        self.assertEquals(
            self.bot.db.get('bat', {}).get('permissions', []),
            [])
        self.assertSent(
            ["PRIVMSG #chan :I don't know bat. Please use --by-id"])

    def test_add_acl_id(self):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(
                ':root@localhost PRIVMSG #chan :!acl add --by-id bak admin')
            yield from asyncio.sleep(0.1)
        self.bot.loop.run_until_complete(wrap())
        self.assertEquals(self.bot.db['bak'].get('permissions'),
                          ['admin'])
        self.assertSent(['PRIVMSG #chan :Updated permissions for bak'])

    def test_invalid_permission(self):

        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(
                ':root@localhost PRIVMSG #chan :!acl add bat fietsen')
            yield from asyncio.sleep(0.1)
        self.bot.loop.run_until_complete(wrap())
        self.assertEquals(
            self.bot.db.get('bat', {}).get('permissions', []),
            [])
        self.assertSent(
            ['PRIVMSG #chan :Invalid permission level. Available permissions: '
             'operator, admin, wiki, view, ignore'])

    def test_remove_acl(self):
        self.bot.db['foo@bar'] = {'permissions': {'admin'}}

        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(
                ':root@localhost PRIVMSG #chan :!acl remove bar admin')
            yield from asyncio.sleep(0.1)
        self.bot.loop.run_until_complete(wrap())
        self.assertEquals(self.bot.db['foo@host'].get('permissions'),
                          [])
