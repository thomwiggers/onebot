from __future__ import unicode_literals

import calendar
import datetime
import json
import os.path

import lastfm.exceptions
from irc3.testing import BotTestCase, patch
from irc3.utils import IrcString


def _get_fixture(fixture_name):
    """Reads a fixture from a file"""
    with open((os.path.dirname(__file__)
               + '/fixtures/{}'.format(fixture_name)), 'r') as f:
        return json.loads(f.read())


def _get_patched_time_fixture(fixture_name, **kwargs):
    """Patches a fixture with a specified time difference

    Options:
        Fixture name
        **kwargs:
            days
            hours
            minutes
            seconds
    """
    fixture = _get_fixture(fixture_name)
    date = datetime.datetime.utcnow()
    date -= datetime.timedelta(**kwargs)
    if not type(fixture['track']) == list:
        fixture['track']['date']['uts'] = str(
            calendar.timegm(date.timetuple()))
        fixture['track']['date']['#text'] = date.strftime('%D %b %Y, %h:%M')
    else:
        fixture['track'][0]['date']['uts'] = str(
            calendar.timegm(date.timetuple()))
        fixture['track'][0]['date']['#text'] = date.strftime('%D %b %Y, %h:%M')
    return fixture


class LastfmPluginTest(BotTestCase):
    """Test the LastFM plugin"""

    config = {
        'includes': ['onebot.plugins.lastfm'],
        'onebot.plugins.lastfm': {'api_key': '',
                                  'api_secret': ''},
        'cmd': '!',
        'database': ':memory:'
    }

    def setUp(self):
        self.bot = self.callFTU()

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_never_played.json'))
    def test_no_user_found(self, mock):
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :!np")
        mock.assert_called_with('bar', extended=True, limit=1)
        self.assertSent(['PRIVMSG #chan :bar is someone who never scrobbled '
                         'before.'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           side_effect=lastfm.exceptions.InvalidParameters('message'))
    def test_lastfm_error_invalid_params(self, mock):
        """InvalidParameters is raised e.g. when a user doesn't exist"""
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        self.assertSent(['PRIVMSG #chan :bar: Error: message'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           side_effect=lastfm.exceptions.OperationFailed('message'))
    def test_lastfm_error(self, mock):
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        self.assertSent(['PRIVMSG #chan :bar: Error: message'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_now_playing_more_results.json'))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_result_now_playing(self, mock_a, mock_b):
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        mock_a.assert_called_with(mbid='010109db-e19e-484f-a0c6-f685b42cd9a6',
                                  username='bar')
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np foo')
        mock_a.assert_called_with(mbid='010109db-e19e-484f-a0c6-f685b42cd9a6',
                                  username='foo')
        self.assertSent(
            ['PRIVMSG #chan :bar is now playing '
             '“M83 – Skin of the Night”.',
             'PRIVMSG #chan :bar (foo on Last.FM) is now playing '
             '“M83 – Skin of the Night”.']
        )

    def test_get_lastfm_nick_from_database(self):
        self.bot.get_database().execute_and_commit_query(
            'INSERT INTO lastfm (lastfmuser, ident, host) VALUES (?, ?, ?)',
            'lastfmuser', 'ident', 'host')
        lastfm = self.bot.get_plugin('onebot.plugins.lastfm.LastfmPlugin')
        assert lastfm.get_lastfm_nick(
            IrcString('nick!ident@host')) == 'lastfmuser'

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, hours=1))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_3_days_1_hour_ago(self, mock, mockb):
        self.bot.dispatch(':bar!id@host PRIVMSG #char :!np')
        self.assertSent(['PRIVMSG #char :bar is not currently playing '
                         'anything (last seen 3 days, 1 hour ago).'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, hours=2))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_3_days_2_hours_ago(self, mock, mockb):
        self.bot.dispatch(':bar!id@host PRIVMSG #char :!np')
        assert not mock.called, "Shouldn't call get_info if play not recent"
        self.assertSent(['PRIVMSG #char :bar is not currently playing '
                         'anything (last seen 3 days, 2 hours ago).'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, minutes=1))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_3_days_1_minute_ago(self, mock, mockb):
        self.bot.dispatch(':bar!id@host PRIVMSG #char :!np')
        assert not mock.called, "Shouldn't call get_info if play not recent"
        self.assertSent(['PRIVMSG #char :bar is not currently playing '
                         'anything (last seen 3 days, 1 minute ago).'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, minutes=2))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_3_days_2_minute_ago(self, mock, mockb):
        self.bot.dispatch(':bar!id@host PRIVMSG #char :!np')
        assert not mock.called, "Shouldn't call get_info if play not recent"
        self.assertSent(['PRIVMSG #char :bar is not currently playing '
                         'anything (last seen 3 days, 2 minutes ago).'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_3_days_ago(self, mock, mockb):
        self.bot.dispatch(':bar!id@host PRIVMSG #char :!np')
        assert not mock.called, "Shouldn't call get_info if play not recent"
        self.assertSent(['PRIVMSG #char :bar is not currently playing '
                         'anything (last seen 3 days ago).'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=1))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_1_day_ago(self, mock, mockb):
        self.bot.dispatch(':bar!id@host PRIVMSG #char :!np')
        assert not mock.called, "Shouldn't call get_info if play not recent"
        self.assertSent(['PRIVMSG #char :bar is not currently playing '
                         'anything (last seen 1 day ago).'])

    # TODO write tests for 'played X 3 minutes ago'
