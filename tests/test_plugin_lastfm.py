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


@asyncio.coroutine
def get_lastfm_nick_mock(nick):
    yield from asyncio.sleep(0.001)
    return nick


@freeze_time("2014-01-01")
@patch('onebot.plugins.users.UsersPlugin', new=MagicMock())
class LastfmPluginTest(BotTestCase):
    """Test the LastFM plugin"""

    config = {
        'includes': ['onebot.plugins.lastfm'],
        'onebot.plugins.lastfm': {'api_key': '',
                                  'api_secret': ''},
        'onebot.plugins.users': {'identified_by': 'mask'},
        'irc3.plugins.command': {
            'antiflood': False
        },
        'cmd': '!',
        'loop': None
    }

    @patch('irc3.plugins.storage.Storage', spec=True)
    def setUp(self, mock):
        super(LastfmPluginTest, self).setUp()
        self.config['loop'] = asyncio.new_event_loop()
        asyncio.set_event_loop(self.config['loop'])
        self.callFTU()
        self.lastfm = self.bot.get_plugin('onebot.plugins.lastfm.LastfmPlugin')
        self.lastfm.get_lastfm_nick = get_lastfm_nick_mock

    def assertSent(self, lines):
        """Assert that these lines have been sent"""
        self.assertEqual(self.bot.sent, lines)

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_never_played.json'))
    def test_no_user_found(self, mock):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(":bar!foo@host PRIVMSG #chan :!np")
            yield from asyncio.sleep(0.11)
            mock.assert_called_with('bar', extended=True, limit=1)
            self.assertSent(['PRIVMSG #chan :bar is someone who never '
                             'scrobbled before.'])
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_never_played.json'))
    def test_dm_works(self, mock):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(":bar!foo@host PRIVMSG #chan :!np")
            yield from asyncio.sleep(0.1)
            self.assertSent(['PRIVMSG bar :bar is someone who never '
                             'scrobbled before.'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           side_effect=lastfm.exceptions.InvalidParameters('message_frommock'))
    def test_lastfm_error_invalid_params(self, mock):
        """InvalidParameters is raised e.g. when a user doesn't exist"""
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
            yield from asyncio.sleep(0.1)
            self.assertSent(['PRIVMSG #chan :bar: Error: message_frommock'])
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           side_effect=lastfm.exceptions.OperationFailed('message'))
    def test_lastfm_error(self, mock):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
            yield from asyncio.sleep(0.1)
            self.assertSent(['PRIVMSG #chan :bar: Error: message'])
        self.bot.loop.run_until_complete(wrap())

    @unittest.skip("FIXME caps don't work")
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_now_playing_more_results.json'))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_np_caps(self, mock_a, mock_b):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':bar!id@host PRIVMSG #chan :!NP')
            mock_a.assert_called_with(
                mbid='010109db-e19e-484f-a0c6-f685b42cd9a6',
                username='bar')
            self.assertSent(
                ['PRIVMSG #chan :bar is now playing '
                 '“M83 – Skin of the Night”.'])
        self.bot.loop.run_until_complete(wrap())

    @unittest.skip("disabled because mbid query is less stable")
    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_now_playing_more_results.json'))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_result_now_playing(self, mock_a, mock_b):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
            yield from asyncio.sleep(0.1)
            mock_a.assert_called_with(
                mbid='010109db-e19e-484f-a0c6-f685b42cd9a6',
                username='bar')
            self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np foo')
            yield from asyncio.sleep(0.1)
            mock_a.assert_called_with(
                mbid='010109db-e19e-484f-a0c6-f685b42cd9a6',
                username='foo')
            self.assertSent(
                ['PRIVMSG #chan :bar is now playing '
                 '“M83 – Skin of the Night”.',
                 'PRIVMSG #chan :bar (foo on Last.FM) is now playing '
                 '“M83 – Skin of the Night”.'])
        self.bot.loop.run_until_complete(wrap())

    def test_get_lastfm_nick_from_database(self):
        mock = MagicMock()

        # mock get_setting
        @asyncio.coroutine
        def mock_get_setting(setting, default):
            assert setting == 'lastfmuser'
            assert default == 'nick'
            return 'lastfmuser'
        mock.get_setting = mock_get_setting
        # we need to have a mock return the mocked user with get_setting
        mock_user = MagicMock(name='MockGetUser', return_value=mock)
        self.callFTU()
        self.bot.get_user = mock_user
        lastfm = self.bot.get_plugin('onebot.plugins.lastfm.LastfmPlugin')

        def wrap():
            lastfmnick = yield from lastfm.get_lastfm_nick('nick')
            assert lastfmnick == 'lastfmuser'
        self.bot.loop.run_until_complete(wrap())

    def test_setuser(self):
        mock = MagicMock(name='MockGetUser')
        del self.config['loop']
        self.callFTU()
        self.bot.get_user = mock
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!setuser foo')
        mock().set_setting.assert_called_with('lastfmuser', 'foo')
        self.assertSent(['PRIVMSG #chan :Ok, so you are '
                         'https://last.fm/user/foo'])

    def test_ignoreme(self):
        mock = MagicMock(name='MockGetUser')
        del self.config['loop']
        self.callFTU()
        self.bot.get_user = mock
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!ignoreme')
        mock().set_setting.assert_called_with('nocompare', True)
        self.assertSent(['PRIVMSG #chan :I will leave out bar from compare. '
                         'Re-enable compare by using the unignoreme command'])

    def test_unignoreme(self):
        mock = MagicMock(name='MockGetUser')
        del self.config['loop']
        self.callFTU()
        self.bot.get_user = mock
        self.bot.dispatch(':bar!id@host PRIVMSG #chan :!unignoreme')
        mock().set_setting.assert_called_with('nocompare', False)
        self.assertSent(['PRIVMSG #chan :Ok, enabled compare for bar'])

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, hours=1))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_days_1_hour_ago(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            yield from asyncio.sleep(0.01)
            assert response == ('bar is not currently playing '
                                'anything (last seen 3 days, 1 hour ago).')
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, hours=2))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_days_2_hours_ago(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            yield from asyncio.sleep(0.01)
            assert response == ('bar is not currently playing '
                                'anything (last seen 3 days, 2 hours ago).')
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, minutes=1))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_days_1_minute_ago(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            yield from asyncio.sleep(0.1)
            assert response == ('bar is not currently playing '
                                'anything (last seen 3 days, 1 minute ago).')
            assert not mock.called, "Shouldn't call get_info if not recent"
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3, minutes=2))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_3_days_2_minutes_ago(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':bar!id@foo PRIVMSG #chan :!np')
            yield from asyncio.sleep(0.1)
            self.assertSent(['PRIVMSG #chan :bar is not currently playing '
                             'anything (last seen 3 days, 2 minutes ago).'])
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@hosta'),
                {'<user>': None})
            assert response == ('bar is not currently playing anything '
                                '(last seen 3 days, 2 minutes ago).')
            assert not mock.called, "Shouldn't call get_info if not recent"
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=3))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_days_ago(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            yield from asyncio.sleep(0.01)
            assert response == ('bar is not currently playing anything '
                                '(last seen 3 days ago).')
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', days=1))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_1_day_ago(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            yield from asyncio.sleep(0.01)
            assert response == ('bar is not currently playing anything '
                                '(last seen 1 day ago).')
            assert not mock.called, "Shouldn't call get_info if not recent"
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_fixture(
               'user_get_recent_tracks_loved_now_playing.json'))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_playing_loved(self, mocka, mockb):
        @asyncio.coroutine
        def wrap():
            self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np')
            yield from asyncio.sleep(0.1)
            self.bot.dispatch(':bar!id@host PRIVMSG #chan :!np foo')
            yield from asyncio.sleep(0.01)
            self.assertSent(
                ['PRIVMSG #chan :bar is now playing '
                 '“Etherwood – Weightless” (♥).',
                 'PRIVMSG #chan :bar (foo on Last.FM) is now playing '
                 '“Etherwood – Weightless” (♥).'])

        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', minutes=3))
    @patch('lastfm.lfm.Track.get_info',
           side_effect=lastfm.exceptions.InvalidParameters)
    def test_lastfm_played_3_minutes_ago(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            assert response == ('bar was just playing '
                                '“M83 – Kim & Jessie” (3m00s ago).')
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played_loved.json', minutes=3))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_graveyard_girl.json'))
    def test_lastfm_played_loved_3_minutes_ago(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            assert response == (
                'bar was just playing “M83 – Kim & Jessie” (♥) (3m00s ago) '
                '(shoegaze, electronic, indie, dream pop, pop).')

        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played_loved.json', minutes=3))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_m83_midnight_city_not_loved_5_plays.json'))
    def test_lastfm_played_loved_count(self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            assert response == (
                'bar was just playing “M83 – Kim & Jessie” (♥) (5 plays) '
                '(3m00s ago) (electronic, indie, electropop, electro, '
                'catchy).')
        self.bot.loop.run_until_complete(wrap())

    @patch('lastfm.lfm.User.get_recent_tracks',
           return_value=_get_patched_time_fixture(
               'user_get_recent_tracks_played.json', minutes=3))
    @patch('lastfm.lfm.Track.get_info',
           return_value=_get_fixture(
               'track_get_info_etherwood_weightless_no_tags_loved.json'))
    def test_lastfm_played_3_minutes_ago_loved_from_extra_info(
            self, mock, mockb):
        @asyncio.coroutine
        def wrap():
            response = yield from self.lastfm.now_playing_response(
                IrcString('bar!id@host'),
                {'<user>': None})
            assert response == ('bar was just playing '
                                '“M83 – Kim & Jessie” (♥) '
                                '(9 plays) (3m00s ago).')

        self.bot.loop.run_until_complete(wrap())


if __name__ == '__main__':
    unittest.main()
