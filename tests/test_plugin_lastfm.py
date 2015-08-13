# -*- coding: utf8 -*-
from __future__ import unicode_literals, print_function

import asyncio
import calendar
import datetime
import json
import os.path
import unittest

import lastfm.exceptions
from freezegun import freeze_time
from irc3.testing import BotTestCase, patch, MagicMock
from irc3.utils import IrcString
import pytest


def _get_fixture(fixture_name):
    """Reads a fixture from a file"""
    with open(
        os.path.join(
            os.path.dirname(__file__),
            'fixtures/{}'.format(fixture_name)), 'r') as f:
        return json.load(f)


@freeze_time("2014-01-01")
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
    date = datetime.datetime.utcnow().replace(microsecond=0)
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


@freeze_time("2014-01-01")
@patch('onebot.plugins.users.UsersPlugin', new=MagicMock())
class LastfmPluginTest(BotTestCase):
    """Test the LastFM plugin"""

    config = {
        'includes': ['onebot.plugins.lastfm'],
        'onebot.plugins.lastfm': {'api_key': '',
                                  'api_secret': ''},
        'onebot.plugins.users': {'identified_by': 'mask'},
        'cmd': '!',
    }

    @patch('irc3.plugins.storage.Storage', spec=True)
    def setUp(self, mock):
        super(LastfmPluginTest, self).setUp()
        self.callFTU()
        self.lastfm = self.bot.get_plugin('onebot.plugins.lastfm.LastfmPlugin')
        self.lastfm.get_lastfm_nick = MagicMock(return_value='bar')

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_never_played.json'))
    def test_no_user_found(self, mock):
        self.bot.dispatch(":bar!foo@host PRIVMSG #chan :!np")
        yield from asyncio.sleep(1)
        assert self.lastfm.get_lastfm_nick.called
        mock.assert_called_with('bar', extended=True, limit=1)
        self.assertSent(['PRIVMSG #chan :bar is someone who never scrobbled '
                         'before.'])

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           side_effect=lastfm.exceptions.InvalidParameters('message'))
    def test_lastfm_error_invalid_params(self, mock):
        """InvalidParameters is raised e.g. when a user doesn't exist"""
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        yield from asyncio.sleep(1)
        self.assertSent(['PRIVMSG #chan :bar: Error: message'])

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           side_effect=lastfm.exceptions.OperationFailed('message'))
    def test_lastfm_error(self, mock):
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        yield from asyncio.sleep(1)
        self.assertSent(['PRIVMSG #chan :bar: Error: message'])

    @unittest.skip("FIXME caps don't work")
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_now_playing_more_results.json'))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_np_caps(self, mock_a, mock_b):
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!NP')
        mock_a.assert_called_with(mbid='010109db-e19e-484f-a0c6-f685b42cd9a6',
                                  username='bar')
        self.assertSent(
            ['PRIVMSG #chan :bar is now playing '
             '“M83 – Skin of the Night”.'])

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_now_playing_more_results.json'))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_result_now_playing(self, mock_a, mock_b):
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        mock_a.assert_called_with(mbid='010109db-e19e-484f-a0c6-f685b42cd9a6',
                                  username='bar')
        yield from asyncio.sleep(1)
        self.lastfm.get_lastfm_nick.reset_mock()
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np foo')
        yield from asyncio.sleep(1)
        mock_a.assert_called_with(mbid='010109db-e19e-484f-a0c6-f685b42cd9a6',
                                  username='foo')
        self.assertSent(
            ['PRIVMSG #chan :bar is now playing '
             '“M83 – Skin of the Night”.',
             'PRIVMSG #chan :bar (foo on Last.FM) is now playing '
             '“M83 – Skin of the Night”.'])

    @pytest.mark.asyncio
    def test_get_lastfm_nick_from_database(self):
        # mock get_setting
        mock2 = MagicMock(name='MockUser')
        mock2.get_setting.return_value = 'lastfmuser'
        # we need to have a mock return the mocked user with get_setting
        mock_user = MagicMock(name='MockGetUser', return_value=mock2)
        self.callFTU()
        self.bot.get_user = mock_user
        lastfm = self.bot.get_plugin('onebot.plugins.lastfm.LastfmPlugin')
        mask = IrcString('nick!ident@host')
        lastfmnick = yield from lastfm.get_lastfm_nick(mask)
        assert lastfmnick == 'lastfmuser'

    @pytest.mark.asyncio
    def test_setuser(self):
        mock = MagicMock(name='MockGetUser')
        self.callFTU()
        self.bot.get_user = mock
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!setuser foo')
        mock().set_setting.assert_called_with('lastfmuser', 'foo')
        self.assertSent(['PRIVMSG #chan :Ok, so you are '
                         'https://last.fm/user/foo'])

    @pytest.mark.asyncio
    def test_ignoreme(self):
        mock = MagicMock(name='MockGetUser')
        self.callFTU()
        self.bot.get_user = mock
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!ignoreme')
        mock().set_setting.assert_called_with('nocompare', True)
        self.assertSent(['PRIVMSG #chan :I will leave out bar from compare. '
                         'Re-enable compare by using the unignoreme command'])

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, hours=1))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_days_1_hour_ago(self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar is not currently playing '
                            'anything (last seen 3 days, 1 hour ago).')

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, hours=2))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_days_2_hours_ago(self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar is not currently playing '
                            'anything (last seen 3 days, 2 hours ago).')

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, minutes=1))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_days_1_minute_ago(self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar is not currently playing '
                            'anything (last seen 3 days, 1 minute ago).')
        assert not mock.called, "Shouldn't call get_info if play not recent"

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, minutes=2))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_3_days_2_minute_ago(self, mock, mockb):
        self.bot.dispatch(':bar!id@foo PRIVMSG #chan :!np')
        self.assertSent(['PRIVMSG #chan :bar is not currently playing '
                         'anything (last seen 3 days, 2 minutes ago).'])
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar is not currently playing anything '
                            '(last seen 3 days, 2 minutes ago).')
        assert not mock.called, "Shouldn't call get_info if play not recent"

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_days_ago(self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar is not currently playing anything '
                            '(last seen 3 days ago).')

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=1))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_1_day_ago(self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar is not currently playing anything '
                            '(last seen 1 day ago).')
        assert not mock.called, "Shouldn't call get_info if play not recent"

    @pytest.mark.asyncio
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_loved_now_playing.json'))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_playing_loved(self, mocka, mockb):
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np foo')
        yield from asyncio.sleep(1)
        self.assertSent(
            ['PRIVMSG #chan :bar is now playing '
             '“Etherwood – Weightless” (♥).',
             'PRIVMSG #chan :bar (foo on Last.FM) is now playing '
             '“Etherwood – Weightless” (♥).'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', minutes=3))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_minutes_ago(self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar was just playing '
                            '“M83 – Kim & Jessie” (3m00s ago).')

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played_loved.json', minutes=3))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_loved_3_minutes_ago(self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar was just playing '
                            '“M83 – Kim & Jessie” (♥) (3m00s ago).')

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played_loved.json', minutes=3))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_midnight_city_not_loved_5_plays.json'))
    def test_lastfm_played_loved_count(self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar was just playing '
                            '“M83 – Kim & Jessie” (♥) '
                            '(5 plays) (3m00s ago).')

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', minutes=3))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_etherwood_weightless_no_tags_loved.json'))
    def test_lastfm_played_3_minutes_ago_loved_from_extra_info(
            self, mock, mockb):
        response = yield from self.lastfm.now_playing_response(
            IrcString('bar!id@host'),
            '#chan',
            {'<user>': None})
        assert response == ('bar was just playing '
                            '“M83 – Kim & Jessie” (♥) '
                            '(9 plays) (3m00s ago).')


if __name__ == '__main__':
    unittest.main()
