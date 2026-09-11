#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_plugin_spotify
-------------------

Tests for the Spotify OAuth callback handler.
"""

import asyncio
import threading
import unittest
from typing import Optional
from urllib.parse import quote

from cryptography.fernet import Fernet
from irc3.utils import IrcString

from onebot.plugins.spotify import SpotifyResponseServer
from onebot.plugins.users import User


class MockDb(dict):
    def set(self, k, **kwargs):
        if not self.get(k):
            self[k] = kwargs
        else:
            self[k].update(**kwargs)


class FakeToken:
    refresh_token = "refresh-token"


class FakeCredentials:
    def __init__(self):
        self.client_token_requested = False

    def request_client_token(self):
        self.client_token_requested = True

    def request_user_token(self, code):
        return FakeToken()


class FakeUser:
    def __init__(self):
        self.settings = {}

    async def set_setting(self, setting, value):
        self.settings[setting] = value


class FakeLog:
    def exception(self, *args, **kwargs):
        pass


class FakeBot:
    def __init__(self, loop, user: Optional[FakeUser]):
        self.loop = loop
        self.user = user
        self.log = FakeLog()
        self.requested_nicks = []

    def get_user(self, nick):
        self.requested_nicks.append(nick)
        return self.user


class FakeWFile:
    def __init__(self):
        self.written = b""

    def write(self, data):
        self.written += data


class FakeHandler:
    """Stand-in for the request handler, so no socket is needed."""

    def __init__(self, bot, key, path):
        self.bot = bot
        self.key = key
        self.path = path
        self.tk_cred = FakeCredentials()
        self.seen = set()
        self.wfile = FakeWFile()
        self.responses = []
        self.errors = []

    def send_response(self, code):
        self.responses.append(code)

    def end_headers(self):
        pass

    def send_error(self, code, message=None, explain=None):
        self.errors.append((code, message))


def make_path(key, nick, code="somecode", ttl_offset=0):
    state = quote(Fernet(key).encrypt(nick.encode()).decode())
    return f"/callback?code={code}&state={state}"


class SpotifyCallbackTestCase(unittest.TestCase):
    def setUp(self):
        self.key = Fernet.generate_key()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self.loop.close()

    def test_stores_token_for_known_user(self):
        user = FakeUser()
        handler = FakeHandler(
            FakeBot(self.loop, user), self.key, make_path(self.key, "bar")
        )

        SpotifyResponseServer._do_callback(handler)

        assert user.settings == {"spotify_refresh_token": "refresh-token"}
        assert handler.responses == [200]
        assert handler.errors == []
        assert b"Stored your token" in handler.wfile.written
        assert "somecode" in handler.seen

    def test_stores_token_for_real_user_object(self):
        """The real User.set_setting path, including async identification"""
        db = MockDb()

        async def id_func():
            # identification is async (nickserv does a WHOIS here)
            await asyncio.sleep(0)
            return "nsaccount"

        user = User(IrcString("bar!foo@host"), [], id_func, db)
        handler = FakeHandler(
            FakeBot(self.loop, user), self.key, make_path(self.key, "bar")
        )

        SpotifyResponseServer._do_callback(handler)

        assert handler.errors == []
        assert handler.responses == [200]
        assert db["nsaccount"] == {"spotify_refresh_token": "refresh-token"}

    def test_unknown_user_does_not_crash(self):
        handler = FakeHandler(
            FakeBot(self.loop, None), self.key, make_path(self.key, "bar")
        )

        SpotifyResponseServer._do_callback(handler)

        assert handler.responses == []
        assert handler.wfile.written == b""
        assert len(handler.errors) == 1
        assert handler.errors[0][0] == 404
        # The code isn't burned, so the user can retry
        assert handler.seen == set()

    def test_failing_store_reports_error(self):
        class FailingUser(FakeUser):
            async def set_setting(self, setting, value):
                raise Exception("database on fire")

        handler = FakeHandler(
            FakeBot(self.loop, FailingUser()), self.key, make_path(self.key, "bar")
        )

        SpotifyResponseServer._do_callback(handler)

        assert handler.responses == []
        assert handler.errors[0][0] == 500
        assert handler.seen == set()

    def test_invalid_state_is_rejected(self):
        other_key = Fernet.generate_key()
        handler = FakeHandler(
            FakeBot(self.loop, FakeUser()), self.key, make_path(other_key, "bar")
        )

        SpotifyResponseServer._do_callback(handler)

        assert handler.errors[0][0] == 403
        assert handler.responses == []

    def test_replayed_code_is_not_processed_twice(self):
        user = FakeUser()
        handler = FakeHandler(
            FakeBot(self.loop, user), self.key, make_path(self.key, "bar")
        )
        handler.seen.add("somecode")

        SpotifyResponseServer._do_callback(handler)

        assert user.settings == {}
        assert handler.responses == [200]
        assert b"already" in handler.wfile.written


if __name__ == "__main__":
    unittest.main()
