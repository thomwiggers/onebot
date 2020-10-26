# -*- coding: utf8 -*-
"""
======================================================
:mod:`onebot.plugins.spotify` Spotify now playing plugin for OneBot
======================================================

..
    >>> import tempfile
    >>> fd = tempfile.NamedTemporaryFile(prefix='irc3', suffix='.json')
    >>> json_file = fd.name
    >>> fd.close()

Usage::

    >>> from onebot.testing import IrcBot, patch
    >>> bot = IrcBot(**{
    ...     'onebot.plugins.spotify': {'client_id': 'foo',
    ...                                'client_secret': 'bar',
    ...                                'redirect_uri': 'http://localhost:9123/callback'},
    ...     'cmd': '!',
    ...     'storage': 'json://%(json_file)s' % {'json_file' : json_file}
    ... })
    >>> bot.include('onebot.plugins.spotify')

"""
import asyncio
import irc3
from irc3.plugins.command import command
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs
import threading
from functools import partial

from cryptography.fernet import Fernet, InvalidToken
import tekore as tk


@irc3.plugin
class LastfmPlugin(object):
    """Plugin to provide:

    * now playing functionality
    """

    requires = [
        "irc3.plugins.command",
        "onebot.plugins.users",
    ]

    def __init__(self, bot):
        """Initialise the plugin"""
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        self.config = bot.config.get(__name__, {})
        client_secret = self.config.get("client_secret")
        client_id = self.config.get("client_id")
        redirect_url = self.config.get("redirect_url")
        self.key = Fernet.generate_key()
        server_address = (
            self.config.get("http_host", "localhost"),
            int(self.config.get("http_port", 9123)),
        )
        server = SpotifyResponseServer
        server.key = self.key
        server.bot = bot
        self.tk_cred = server.tk_cred = tk.RefreshingCredentials(
            client_id, client_secret, redirect_url
        )
        http_server = ThreadingHTTPServer(server_address, server)
        self.server_thread = threading.Thread(target=http_server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

    @command
    async def sp(self, mask, target, args):
        """
        Show currently playing track via Spotify. Needs to be authed.

            %%sp
        """
        token = await self.get_spotify_token(mask.nick)
        if not token:
            return "Log in with spotify first via setspotifyuser"
        spotify = tk.Spotify(token, asynchronous=True)
        currently_playing = await spotify.playback_currently_playing()

        if currently_playing is None or currently_playing.item is None:
            return f"{mask.nick} is not playing anything at the moment."

        playing_type = currently_playing.currently_playing_type
        if playing_type == tk.model.CurrentlyPlayingType.track:
            track = currently_playing.item
            artists = ", ".join(artist.name for artist in track.artists)
            album = track.album
            response = f"{mask.nick} is playing {artists} - “{track.name}”"
            if album.name != track.name:
                response += f" (“{album.name}”)"
            response += f" ({album.release_date[:4]})"
            response += f" ({track.uri})"
            return response
        elif playing_type == tk.model.CurrentlyPlayingType.ad:
            return "You're playing an ad!"
        elif playing_type == tk.model.CurrentlyPlayingType.episode:
            episode = currently_playing.item
            response = f"{mask.nick} is listening to episode “{episode.name}” from “{episode.show.name}”"
            return response
        else:
            return f"{mask.nick} is listening to something, but I don't know what (type: {playing_type})"

    async def get_spotify_token(self, nick):
        user = self.bot.get_user(nick)
        if not user:
            return None
        result = await user.get_setting("spotify_refresh_token")
        if not result:
            return None
        new_token = self.tk_cred.refresh_user_token(result)
        user.set_setting("spotify_refresh_token", new_token.refresh_token)
        return new_token

    @command
    def setspotifyuser(self, mask, target, args):
        """
        Sets the lastfm username of the user

            %%setspotifyuser
        """
        fernet = Fernet(self.key)
        state = fernet.encrypt(mask.nick.encode()).decode()

        auth_url = self.tk_cred.user_authorisation_url(
            scope=tk.scope.user_read_currently_playing,
            state=state,
        )

        self.bot.privmsg(mask.nick, f"Authorize me here: {auth_url}")
        return "I've sent you a PRIVMSG with instructions"

    @classmethod
    def reload(cls, old):  # pragma: no cover
        old.server_thread.shutdown()
        newinstance = cls(old.bot)
        newinstance.key = old.key
        return newinstance


class SpotifyResponseServer(BaseHTTPRequestHandler):
    key = None
    bot = None
    seen = set()

    def do_GET(self):
        """Handle GET requests"""
        self.close_connection = True

        print(f"Request: {self.path}")
        if self.path.startswith("/callback?"):
            self._do_callback()
        else:
            self.send_error(404)

    def _do_callback(self):
        self.tk_cred.request_client_token()
        fernet = Fernet(self.key)
        code = tk.parse_code_from_url(self.path)
        if code in self.seen:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Processed your token already")
            return
        self.seen.add(code)
        try:
            qs = self.path[len("/callback?") :]
            params = parse_qs(qs)
            state = fernet.decrypt(params["state"][0].encode(), ttl=120).decode()
            user = self.bot.get_user(state)
            user_token = self.tk_cred.request_user_token(code)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Stored your token")
            self.bot.loop.call_soon_threadsafe(
                user.set_setting, "spotify_refresh_token", user_token.refresh_token
            )
        except InvalidToken:
            self.send_error(403, message="Token expired, try again")
        except tk.BadRequest as e:
            self.send_error(500, message=f"exception: {e}")
