#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_urlinfo
----------------------------------

Tests for urlinfo module.
"""

import os.path
from unittest.mock import MagicMock
from pathlib import Path

from irc3.testing import BotTestCase
from onebot.plugins.urlinfo import UrlSkipException, _find_urls

from .test_plugin_users import MockDb


def mock_requests_get(*args, **kwargs):
    """Mock a response object"""
    class MockResponse:
        """Mocked response object"""
        def __init__(self, *args, **kwargs):
            self.ok = True
            self._file_name = Path(os.path.dirname(__file__)
                                   ).joinpath('fixtures/fb-example.html')
            self._file_size = self._file_name.stat().st_size
            self.headers = {
                'Content-Type': 'text/html',
                'Content-Length': '{}'.format(self._file_size),
            }
            self.content = self._file_name.read_bytes()
            self._filehandle = self._file_name.open()

        def close(self, *args, **kwargs):
            self._filehandle.close()

    return MockResponse()


class UrlInfoTestCase(BotTestCase):
    """Test the URLInfo module"""

    config = {
        'includes': [
            'onebot.plugins.urlinfo',
            'irc3.plugins.command'
        ],
        'cmd': '!'
    }

    def setUp(self):
        """Set up the test class"""
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
            ('(http://nos.nl/(test))', ['http://nos.nl/(test)']),
            ('http://nos.nl/(test)test)', ['http://nos.nl/(test)test']),
            ('<http://nos.nl/test>', ['http://nos.nl/test']),
        ]:
            self.assertEqual(expected, _find_urls(message),
                             "String: {}".format(message))

    def test_too_long_title_text(self):
        """Don't show very long title texts"""
        session = MagicMock()
        session.get.side_effect = mock_requests_get
        result = self.plugin._process_url(session, 'http://facebooktest.com')
        self.assertLess(100, len(' '.join(result)), "text too short")
        self.assertGreater(320, len(' '.join(result)), "text too long")
