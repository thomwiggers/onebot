import unittest
from unittest.mock import MagicMock, patch
import socket
import requests
from betamax import Betamax
from onebot.plugins.urlinfo import UrlInfo


with Betamax.configure() as config:
    config.cassette_library_dir = "tests/fixtures/cassettes"


class MediaWikiUrlInfoTestCase(unittest.TestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.bot.config = {
            "onebot.plugins.urlinfo": {
                "mediawiki_sites": {
                    "wiki.example.com": {
                        "api_url": "https://wiki.example.com/api.php",
                        "username": "BotUser",
                        "password": "BotPassword",
                    },
                    "en.wikipedia.org": {
                        "api_url": "https://en.wikipedia.org/w/api.php",
                    },
                }
            }
        }
        self.bot.log = MagicMock()
        self.plugin = UrlInfo(self.bot)

    def test_wikipedia(self):
        with requests.Session() as session:
            session.headers.update({"User-Agent": "script:onebot:irc"})
            with Betamax(session).use_cassette("wikipedia"):
                for url, expected in [
                    (
                        "https://en.wikipedia.org/wiki/Python_(programming_language)",
                        [
                            "“Python (programming language)”",
                            "— Python is a high-level, general-purpose programmi…",
                        ],
                    ),
                    (
                        "https://en.wikipedia.org/w/index.php?title=IRC",
                        [
                            "“IRC”",
                            "— IRC (Internet Relay Chat) is a text-based chat sy…",
                        ],
                    ),
                ]:
                    with self.subTest(url=url):
                        result = self.plugin._process_url(session, url)
                        self.assertEqual(result, expected)

    @patch("socket.getaddrinfo")
    def test_mediawiki_login_and_fetch(self, mock_getaddrinfo):
        # Allow wiki.example.com (public IP)
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]

        session = MagicMock()
        url = "https://wiki.example.com/wiki/Some_Page"

        # Mock responses
        def side_effect(method, url, **kwargs):
            if "api.php" not in url:
                return MagicMock(ok=False, status_code=404)

            params = kwargs.get("params", {})
            data = kwargs.get("data", {})

            if method == "GET" and params.get("meta") == "tokens":
                return MagicMock(
                    ok=True,
                    json=lambda: {
                        "query": {"tokens": {"logintoken": "EXAMPLE_LOGIN_TOKEN"}}
                    },
                )

            if method == "POST" and data.get("action") == "login":
                if (
                    data["lgname"] == "BotUser"
                    and data["lgpassword"] == "BotPassword"
                    and data["lgtoken"] == "EXAMPLE_LOGIN_TOKEN"
                ):
                    return MagicMock(
                        ok=True, json=lambda: {"login": {"result": "Success"}}
                    )
                return MagicMock(ok=True, json=lambda: {"login": {"result": "Failed"}})

            if method == "GET" and params.get("prop") == "extracts|info":
                return MagicMock(
                    ok=True,
                    json=lambda: {
                        "query": {
                            "pages": {
                                "123": {
                                    "pageid": 123,
                                    "title": "Some Page",
                                    "extract": "This is a very long extract that should be truncated because it exceeds fifty characters in total length.",
                                    "length": 1000,
                                    "touched": "2023-01-01T00:00:00Z",
                                    "lastrevid": 500,
                                }
                            }
                        }
                    },
                )

            return MagicMock(ok=False, status_code=400)

        session.get.side_effect = lambda u, **k: side_effect("GET", u, **k)
        session.post.side_effect = lambda u, **k: side_effect("POST", u, **k)

        result = self.plugin._process_url(session, url)

        self.assertIsNotNone(result)
        # "This is a very long extract that should be trunc…" (length 49 + …)
        # "This is a very long extract that should be trunc" is 49 chars.
        # "This is a very long extract that should be trunca" is 50 chars.
        # The code does: if len(summary) > 50: summary = summary[:49] + "…"
        expected_summary = "— This is a very long extract that should be trunca…"
        self.assertEqual(result, ["“Some Page”", expected_summary])
        self.assertLessEqual(len(result[1]) - 2, 50)  # -2 for "— "

    @patch("socket.getaddrinfo")
    def test_mediawiki_partial_html(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        session = MagicMock()
        url = "https://wiki.example.com/wiki/Partial_Page"

        def side_effect(method, url, **kwargs):
            params = kwargs.get("params", {})
            if method == "GET" and params.get("prop") == "extracts|info":
                return MagicMock(
                    ok=True,
                    json=lambda: {
                        "query": {
                            "pages": {
                                "124": {
                                    "pageid": 124,
                                    "title": "Partial Page",
                                    "extract": "This is a partial tag",
                                    "length": 100,
                                }
                            }
                        }
                    },
                )
            return MagicMock(
                ok=True, json=lambda: {"query": {"tokens": {"logintoken": "tok"}}}
            )

        session.get.side_effect = lambda u, **k: side_effect("GET", u, **k)
        session.post.return_value = MagicMock(
            ok=True, json=lambda: {"login": {"result": "Success"}}
        )

        result = self.plugin._process_url(session, url)
        self.assertIsNotNone(result)
        self.assertEqual(result, ["“Partial Page”", "— This is a partial tag"])

        # Verify calls
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(session.post.call_count, 1)

    @patch("socket.getaddrinfo")
    def test_mediawiki_login_caching(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        session = MagicMock()
        url = "https://wiki.example.com/wiki/Some_Page"

        def side_effect(method, url, **kwargs):
            params = kwargs.get("params", {})
            if method == "GET" and params.get("meta") == "tokens":
                return MagicMock(
                    ok=True, json=lambda: {"query": {"tokens": {"logintoken": "tok"}}}
                )
            return MagicMock(
                ok=True,
                json=lambda: {
                    "query": {"pages": {"1": {"title": "T", "extract": "E"}}}
                },
            )

        session.get.side_effect = lambda u, **k: side_effect("GET", u, **k)
        session.post.return_value = MagicMock(
            ok=True, json=lambda: {"login": {"result": "Success"}}
        )

        # First call: should login
        self.plugin._process_url(session, url)
        self.assertEqual(session.post.call_count, 1)
        self.assertIn("wiki.example.com", self.plugin.mediawiki_logged_in)

        # Second call: should NOT login
        session.reset_mock()
        session.get.side_effect = lambda u, **k: side_effect("GET", u, **k)
        session.post.return_value = MagicMock(
            ok=True, json=lambda: {"login": {"result": "Success"}}
        )

        self.plugin._process_url(session, url)

        self.assertEqual(session.post.call_count, 0)

    @patch("socket.getaddrinfo")
    def test_mediawiki_retry_login(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]

        session = MagicMock()

        url = "https://wiki.example.com/wiki/Secret_Page"

        # Pre-populate cache to simulate expired session

        self.plugin.mediawiki_logged_in.add("wiki.example.com")

        def side_effect(method, url, **kwargs):
            params = kwargs.get("params", {})

            if method == "GET":
                if params.get("meta") == "tokens":
                    return MagicMock(
                        ok=True,
                        json=lambda: {"query": {"tokens": {"logintoken": "new_tok"}}},
                    )

                if params.get("prop") == "extracts|info":
                    # First attempt: access denied

                    if session.post.call_count == 0:
                        return MagicMock(
                            ok=True, json=lambda: {"error": {"code": "readapidenied"}}
                        )

                    # Second attempt: success

                    return MagicMock(
                        ok=True,
                        json=lambda: {
                            "query": {
                                "pages": {
                                    "125": {
                                        "pageid": 125,
                                        "title": "Secret Page",
                                        "extract": "Shh",
                                        "length": 100,
                                    }
                                }
                            }
                        },
                    )

            return MagicMock(ok=False)

        session.get.side_effect = lambda u, **k: side_effect("GET", u, **k)

        session.post.return_value = MagicMock(
            ok=True, json=lambda: {"login": {"result": "Success"}}
        )

        result = self.plugin._process_url(session, url)

        self.assertIsNotNone(result)

        self.assertEqual(result, ["“Secret Page”", "— Shh"])

        # Should have called login once (retry)

        self.assertEqual(session.post.call_count, 1)

        self.assertIn("wiki.example.com", self.plugin.mediawiki_logged_in)
