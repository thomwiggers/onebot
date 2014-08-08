# -*- coding: utf8 -*-
"""
======================================================
:mod:`onebot.plugins.lastfm` Last.FM plugin for OneBot
======================================================

Usage::

    >>> from irc3.testing import IrcBot
    >>> bot = IrcBot(**{
    ...     'onebot.plugins.lastfm': {'api_key': 'foo',
    ...                               'api_secret': 'bar'},
    ...     'cmd': '!'
    ... })
    >>> bot.include('onebot.plugins.lastfm')

In-channel::

    >>> # These examples will produce error messages since we don't have
    >>> # a valid API key
    >>> bot.test(':foo!m@h PRIVMSG #chan :!np')
    PRIVMSG #chan :foo: Fatal exception occurred. Aborting
    >>> bot.test(':bar!m@h PRIVMSG #chan :!np foo')
    PRIVMSG #chan :foo: Fatal exception occurred. Aborting

"""
from __future__ import unicode_literals, print_function, absolute_import

import datetime
import logging
import math

import irc3
import lastfm.exceptions
from irc3.plugins.command import command
from lastfm import lfm


@irc3.plugin
class LastfmPlugin(object):
    """Plugin to provide:

    * now playing functionality
    * compare users' lastfm accounts through the tasteometer.
    """

    requires = [
        'irc3.plugins.command'
    ]

    def __init__(self, bot):
        """Initialise the plugin"""
        self.bot = bot
        self.log = logging.getLogger(__name__)
        self.config = bot.config.get(__name__, {})
        try:
            self.app = lfm.App(self.config['api_key'],
                               self.config['api_secret'],
                               self.config.get('cache_file'))
        except KeyError:  # pragma: no cover
            raise Exception(
                "You need to set the Last.FM api_key and api_secret "
                "in the config section [{}]".format(__name__))

    @command
    def np(self, mask, target, args):
        """Show currently playing track

            %%np [<user>]
        """
        user = args['<user>'] or self.get_lastfm_nick(mask)
        try:
            result = self.app.user.get_recent_tracks(
                user,
                limit=1,
                extended=True)
        except lastfm.exceptions.InvalidParameters:
            self.log.exception("Exception when calling last.fm")
            self.bot.privmsg(target,
                             "{user}: Exception when calling last.fm"
                             .format(user=user))
        except Exception:
            self.log.exception("Fatal exception when calling last.fm")
            self.bot.privmsg(target,
                             "{user}: Fatal exception occurred. "
                             "Aborting".format(user=user))
        else:
            response = ["{user}".format(user=user)]
            if 'track' not in result:
                response.append("is someone who never scrobbled before.")
            else:
                track = result['track']
                # The API might return a list. Strip it off.
                if isinstance(track, list):
                    track = result['track'][0]
                info = _parse_trackinfo(track)
                info = self.fetch_extra_trackinfo(user, info)

                time_ago = datetime.datetime.now() - info['playtime']
                if time_ago.days > 0 or time_ago.seconds > (20*60):
                    if time_ago.days > 0:
                        timestr = "{days} days, {minutes} minutes".format(
                            days=time_ago.days,
                            minutes=math.floor(time_ago.seconds/60))
                    else:
                        timestr = "{minutes} minutes".format(
                            minutes=math.floor(time_ago.seconds/60))
                    response.append('is not currently playing anything '
                                    '(last seen {time} ago).'.format(
                                        time=timestr))

                    self.bot.privmsg(target, ' '.join(response))
                    return

                if info['now playing']:
                    response.append('is now playing')
                else:
                    response.append('was just playing')

                response.append(u'“{artist} – {title}”'.format(
                    artist=info['artist'],
                    title=info['title']))

                if info['loved']:
                    response.append(u'(♥)')

                if not info['now playing']:

                    minutes = math.floor(time_ago.seconds / 60)
                    seconds = time_ago.seconds % 60
                    if minutes > 0:
                        response.append("({}m{}s ago)".format(minutes,
                                                              seconds))
                    else:
                        response.append("({}s ago)".format(seconds))

            self.bot.privmsg(target, ' '.join(response) + '.')

    def get_lastfm_nick(self, mask):
        """Gets the last.fm nick associated with a user"""
        return mask.nick

    def fetch_extra_trackinfo(self, username, info):
        """Updates info with extra trackinfo from the last.fm API"""
        if 'mbid' in info:
            api_result = self.app.track.get_info(mbid=info['mbid'],
                                                 username=username)
        else:
            api_result = self.app.track.get_info(track=info['title'],
                                                 artist=info['artist'],
                                                 username=username)

        if 'userplaycount' in api_result:
            info['playcount'] = api_result['userplaycount']

        if 'toptags' in api_result:
            info['tags'] = [tag['name'] for tag in api_result['toptags']]

        if 'userloved' in api_result and not info['loved']:
            info['loved'] = bool(int(api_result['userloved']))


def _parse_trackinfo(track):
    """Parses the track info into something more comprehensible

    >>> dictionary = {
    ...             'artist': {
    ...                 'image':
    ...                 [{'#text':
    ...                   'http://userserve-ak.last.fm/serve/34/89024929.png',
    ...                   'size': 'small'},
    ...                  {'#text':
    ...                   'http://userserve-ak.last.fm/serve/64/89024929.png',
    ...                   'size': 'medium'},
    ...                  {'#text':
    ...                   'http://userserve-ak.last.fm/serve/126/89024929.png',
    ...                   'size': 'large'},
    ...                  {'#text':
    ...                   'http://userserve-ak.last.fm/serve/252/89024929.png',
    ...                   'size': 'extralarge'}],
    ...                 'mbid': '8dc08b1f-e393-4f85-a5dd-300f7693a8b8',
    ...                 'url': 'James Blake', 'name': 'James Blake'},
    ...             'album': {'mbid': '809bf04c-b498-46e8-8aab-3dceb37cc4a5',
    ...                       '#text': 'Overgrown'},
    ...             'url': 'http://www.last.fm/music/James+Blake/_/I+Am+Sold',
    ...             'name': 'I Am Sold',
    ...             'image': [{
    ...                 '#text':
    ...                 'http://userserve-ak.last.fm/serve/34s/88946193.png',
    ...                 'size': 'small'},
    ...                 {'#text':
    ...                  'http://userserve-ak.last.fm/serve/64s/88946193.png',
    ...                  'size': 'medium'},
    ...                 {'#text':
    ...                  'http://userserve-ak.last.fm/serve/126/88946193.png',
    ...                  'size': 'large'},
    ...                 {'#text':
    ...                  ('http://userserve-ak.last.fm/serve/300x300/'
    ...                  '88946193.png'),
    ...                  'size': 'extralarge'}],
    ...             'date': {'#text': '6 Aug 2014, 13:39',
    ...                      'uts': '1407332359'},
    ...             'streamable': '0',
    ...             'loved': '0',
    ...             'mbid': '65af6bac-56af-4744-aa8a-8f7a8605b2c1'}
    >>> a = _parse_trackinfo(dictionary)
    >>> a['playtime']  # doctest: +ELLIPSIS
    datetime.datetime(2014, 8, 6, ...)
    >>> del a['playtime']
    >>> a == {
    ...     'artist': 'James Blake',
    ...     'album': 'Overgrown',
    ...     'loved': False,
    ...     'now playing': False,
    ...     'title': 'I Am Sold',
    ...     'mbid': '65af6bac-56af-4744-aa8a-8f7a8605b2c1'}
    True
    >>> dictionary['@attr'] = {'nowplaying': 'true'}
    >>> a = _parse_trackinfo(dictionary)
    >>> # Patch playtime to make it testable
    >>> del a['playtime']
    >>> a == {
    ...     'artist': 'James Blake',
    ...     'album': 'Overgrown',
    ...     'loved': False,
    ...     'now playing': True,
    ...     'title': 'I Am Sold',
    ...     'mbid': '65af6bac-56af-4744-aa8a-8f7a8605b2c1'}
    True

    """
    now_playing = False
    if '@attr' in track and 'nowplaying' in track['@attr']:
        now_playing = bool(track['@attr']['nowplaying'])
        playtime = datetime.datetime.now()
    else:
        playtime = datetime.datetime.fromtimestamp(int(track['date']['uts']))

    loved = False
    if 'loved' in track:
        loved = bool(int(track['loved']))

    result = {
        'title': track['name'],
        'artist': track['artist']['name'],
        'album': track['album']['#text'],
        'now playing': now_playing,
        'loved': loved,
        'playtime': playtime}

    if 'mbid' in track:
        result['mbid'] = track['mbid']

    return result
