#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_onebot_urlinfo
----------------------------------

Tests for urlinfo module.
"""

import os.path
import logging
import unittest
from unittest.mock import MagicMock
from pathlib import Path

from onebot.testing import BotTestCase
from onebot.plugins.urlinfo import _find_urls

import requests

from .test_plugin_users import MockDb


def mock_requests_get(*args, **kwargs):
    """Mock a response object"""

    class MockResponse:
        """Mocked response object"""

        status_code = 200

        def __init__(self, *args, **kwargs):
            self.ok = True
            self._file_name = Path(os.path.dirname(__file__)).joinpath(
                "fixtures/fb-example.html"
            )
            self._file_size = self._file_name.stat().st_size
            self.headers = {
                "Content-Type": "text/html",
                "Content-Length": "{}".format(self._file_size),
            }
            self.content = self._file_name.read_bytes()
            self._filehandle = self._file_name.open()

        def close(self, *args, **kwargs):
            self._filehandle.close()

    return MockResponse()


class UrlInfoTestCase(BotTestCase):
    """Test the URLInfo module"""

    config = {
        "includes": ["onebot.plugins.urlinfo", "irc3.plugins.command"],
        "cmd": "!",
        "onebot.plugins.urlinfo": {"twitter_bearer_token": "foo"},
    }

    def setUp(self):
        """Set up the test class"""
        super(UrlInfoTestCase, self).setUp()
        self.callFTU()
        self.bot.db = MockDb({"the@boss": {"permissions": {"all_permissions"}}})
        self.bot.log = logging.getLogger("test")
        self.bot.log.setLevel(logging.DEBUG)
        self.plugin = self.bot.get_plugin("onebot.plugins.urlinfo.UrlInfo")

    def test_skip_localhost(self):
        """Assert localhosts are skipped"""

        def crash(slf, *args, **kwargs):
            self.fail("Shouldn't reach process_url_default")

        self.plugin._process_url_default = crash
        self.assertFalse(self.plugin._process_url(None, "http://localhost"))
        self.assertFalse(self.plugin._process_url(None, "http://localhost/test"))
        self.assertFalse(self.plugin._process_url(None, "http://localhost.local"))
        self.assertFalse(self.plugin._process_url(None, "http://localhost.localdomain"))
        self.assertFalse(self.plugin._process_url(None, "http://[::1]/"))
        self.assertFalse(self.plugin._process_url(None, "http://10.0.0.1/"))

    def test_url_finder(self):
        for message, expected in [
            ("https://nos.nl", ["https://nos.nl"]),
            ("Ga naar https://nos.nl.", ["https://nos.nl"]),
            ("Ga naar https://nos.nl,", ["https://nos.nl"]),
            (
                "Ga naar https://nos.nl, https://nos.nl",
                ["https://nos.nl", "https://nos.nl"],
            ),
            ("https://nos.nl/test)", ["https://nos.nl/test"]),
            ("http://nos.nl:80/test)", ["http://nos.nl:80/test"]),
            ("http://nos.nl:80/(test)", ["http://nos.nl:80/(test)"]),
            ("(http://nos.nl/(test))", ["http://nos.nl/(test)"]),
            ("http://nos.nl/(test)test)", ["http://nos.nl/(test)test"]),
            ("<http://nos.nl/test>", ["http://nos.nl/test"]),
        ]:
            self.assertEqual(
                expected, _find_urls(message), "String: {}".format(message)
            )

    def test_too_long_title_text(self):
        """Don't show very long title texts"""
        session = MagicMock()
        session.get.side_effect = mock_requests_get
        result = self.plugin._process_url(session, "https://facebook.com")
        self.assertIsNotNone(result)
        self.assertLess(100, len(" ".join(result)), "text too short")
        self.assertGreater(320, len(" ".join(result)), "text too long")

    def test_twitter(self):
        self.assertEqual(self.plugin.twitter_bearer_token, "foo")
        if "TWITTER_BEARER_TOKEN" not in os.environ:
            raise unittest.SkipTest("no twitter api key")
        self.plugin.twitter_bearer_token = os.environ["TWITTER_BEARER_TOKEN"]
        with requests.Session() as session:
            for (url, expected) in [
                (
                    "https://twitter.com/jack/status/20",
                    "jack⚡️ (@jack ✅): just setting up my twttr",
                ),
                (
                    "https://mobile.twitter.com/jack/status/20",
                    "jack⚡️ (@jack ✅): just setting up my twttr",
                ),
                (
                    "https://twitter.com/Hyves",
                    "Hyves Games (@Hyves) — Stel hier je vragen aan de Support afdeling van Hyves Games en volg ons voor updates! Volg @hyves voor nieuws over de website.",
                ),
                (
                    "https://twitter.com/realdonaldtrump/",
                    "Error: User has been suspended: [realdonaldtrump].",
                ),
                (
                    "https://twitter.com/thomwigggers",
                    "Error: Could not find user with username: [thomwigggers].",
                ),
                (
                    "https://twitter.com/Twitter/status/1278763679421431809",
                    "Twitter (@Twitter ✅): You can have an edit button when everyone wears a mask",
                ),
                (
                    "https://twitter.com/Twitter/status/1274087694105075714",
                    "Twitter (@Twitter ✅): @Twitter 📍 New York City 🗣️ @Afrikkana95 https://t.co/tEfs27p7xu",
                ),
                ("https://twitter.com/Twitter/status/13", "Tweet not found."),
                # we don't match this one because otherwise we can be an ID tweet oracle
                ("https://twitter.com/i/web/status/1440605916642959371", "Twitter"),
            ]:
                with self.subTest(url=url):
                    result = self.plugin._process_url(session, url)
                    self.assertEqual(" ".join(result), expected)

    def test_reddit(self):
        with requests.Session() as session:
            session.headers.update(
                {
                    "User-Agent": (
                        "linux:onebot:1 by DutchDudeWCD " "(Compatible: curl/7.61)"
                    ),
                    "Accept-Language": "en-GB, en-US, en, nl-NL, nl",
                }
            )
            for (url, expected) in [
                ("https://reddit.com/u/DutchDudeWCD", "/u/DutchDudeWCD on Reddit"),
                (
                    "https://www.reddit.com/r/crypto/comments/7jrba2/crypto_is_not_cryptocurrency/",
                    "/r/crypto: Crypto is not cryptocurrency",
                ),
                (
                    "https://www.reddit.com/r/crypto/comments/5vqe47/announcing_the_first_sha1_collision/de3ywos/?context=3",
                    "/r/crypto comment by Natanael_L on “Announcing the first SHA1 collision”",
                ),
            ]:
                with self.subTest(url=url):
                    result = self.plugin._process_url(session, url)
                    self.assertEqual(" ".join(result), expected)
