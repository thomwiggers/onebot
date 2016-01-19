#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_urlinfo
----------------------------------

Tests for urlinfo module.
"""

from irc3.testing import BotTestCase
from onebot.plugins.urlinfo import UrlSkipException, _find_urls

from .test_plugin_users import MockDb


class UrlInfoTestCase(BotTestCase):

    config = {
        'includes': [
            'onebot.plugins.urlinfo',
            'irc3.plugins.command'
        ],
        'cmd': '!'
    }

    def setUp(self):
        super(UrlInfoTestCase, self).setUp()
        self.callFTU()
        self.bot.db = MockDb({
            'the@boss': {'permissions': {'all_permissions'}}
        })
        self.plugin = self.bot.get_plugin('onebot.plugins.urlinfo.UrlInfo')

    def test_skip_localhost(self):
        """Assert localhosts are skipped"""
        def crash(slf, *args, **kwargs):
            self.fail("Shouldn't reach process_url_default")
        self.plugin._process_url_default = crash
        self.assertFalse(self.plugin._process_url(None, 'http://localhost'))
        self.assertFalse(
            self.plugin._process_url(None, 'http://localhost/test'))
        self.assertFalse(
            self.plugin._process_url(None, 'http://localhost.local'))
        self.assertFalse(
            self.plugin._process_url(None, 'http://localhost.localdomain'))
        self.assertFalse(self.plugin._process_url(None, 'http://[::1]/'))
        self.assertFalse(self.plugin._process_url(None, 'http://10.0.0.1/'))

    def test_skip_reddit(self):
        with self.assertRaises(UrlSkipException):
            self.plugin._process_url_reddit(None, 'https://reddit.com')
        with self.assertRaises(UrlSkipException):
            self.plugin._process_url_reddit(None, 'https://np.reddit.com')

    def test_url_finder(self):
        for message, expected in [
            ('https://nos.nl', ['https://nos.nl']),
            ('Ga naar https://nos.nl.', ['https://nos.nl']),
            ('Ga naar https://nos.nl,', ['https://nos.nl']),
            ('Ga naar https://nos.nl, https://nos.nl',
             ['https://nos.nl', 'https://nos.nl']),
            ('https://nos.nl/test)', ['https://nos.nl/test']),
            ('http://nos.nl:80/test)', ['http://nos.nl:80/test']),
            ('http://nos.nl:80/(test)', ['http://nos.nl:80/(test)']),
            ('<http://nos.nl/test>', ['http://nos.nl/test']),
        ]:
            self.assertEqual(expected, _find_urls(message),
                             "String: {}".format(message))
