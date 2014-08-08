from unittest import skip
from irc3.testing import BotTestCase, patch

import lastfm.exceptions


class LastfmPluginTest(BotTestCase):

    """Test the LastFM plugin"""

    config = {
        'includes': ['onebot.plugins.lastfm'],
        'onebot.plugins.lastfm': {'api_key': '',
                                  'api_secret': ''},
        'cmd': '!'
    }

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value={"error": 6,
                         "message": "No user with that name was found",
                         "links": []})
    def test_no_user_found(self, mock):
        bot = self.callFTU()
        bot.dispatch(":bar!foo@host PRIVMSG #chan :!np")
        mock.assert_called_with('bar', extended=True, limit=1)
        self.assertSent(['PRIVMSG #chan :bar is someone who never scrobbled '
                         'before.'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_error(self, mock):
        bot = self.callFTU()
        bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        self.assertSent(['PRIVMSG #chan :bar: Exception when calling last.fm'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value={
               "track": [{
                   "@attr": {
                       "nowplaying": "true"},
                   "artist": {
                       "name": "The Weeknd",
                       "mbid": "c8b03190-306c-4120-bb0b-6f2ebfc06ea9"},
                   "name": "Wanderlust",
                   "streamable": "0",
                   "mbid": "",
                   "album": {"#text": "Kiss Land",
                             "mbid": "5ca11d91-064f-4ad8-9af5-27639ded7ea7"},
                   "url": "The+WeeknWanderlust",
                   "image": [{"#text": "last.fm\/serve\/34s\/91697657.png",
                              "size": "small"},
                             {"#text": "fm\/serve\/64s\/91697657.png",
                              "size": "medium"},
                             {"#text": "serve\/126\/91697657.png",
                              "size": "large"},
                             {"#text": "u1697657.png",
                              "size": "extralarge"}]}],
               "@attr": {"user": "RJ",
                         "page": "1",
                         "perPage": "1",
                         "totalPages": "72651",
                         "total": "72651"}})
    @patch('lastfm.lfm.Track.get_info',
           return_value={
               'userplaycount': 0,
               'toptags': {
                   'tags': [
                       {'name': 'foo'},
                       {'name': 'bar'},
                       {'name': 'foobar'}]},
               'userloved': False})
    def test_lastfm_result_now_playing_no_mbid(self, mock_a, mock_b):
        bot = self.callFTU()

        bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        bot.dispatch(':bar!id@host PRIVMSG #chan :!np foo')
        self.assertSent(
            ['PRIVMSG #chan :bar is now playing '
             '“The Weeknd – Wanderlust”.',
             'PRIVMSG #chan :bar (foo on Last.FM) is now playing '
             '“The Weeknd – Wanderlust”.']
        )

    @skip
    @patch('lastfm.lfm.user.get_recent_tracks.__call__',
           return_value=None)  # TODO
    def test_lastfm_result_just_playing(self):
        bot = self.callFTU()
        bot.dispatch(':bar!id@host PRIVMSG #char :!np')
