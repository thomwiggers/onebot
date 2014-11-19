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
    ...     'cmd': '!',
    ...     'database': ':memory:'
    ... })
    >>> bot.include('onebot.plugins.lastfm')

"""
from __future__ import unicode_literals, print_function, absolute_import

import datetime
import logging

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
        'irc3.plugins.command',
        'onebot.plugins.database',
        'onebot.plugins.users'
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
                "You need to set the Last.FM api_key and api_scret "
                "in the config section [{}]".format(__name__))

        if not self.bot.get_database().fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name=?", 'lastfm'):
            self._init_database()

    @command
    def np(self, mask, target, args):
        """Show currently playing track

            %%np [<user>]
        """
        self.bot.privmsg(target, self.now_playing_response(mask, target, args))

    def now_playing_response(self, mask, target, args):
        """Return appropriate response to np request"""
        lastfm_user = args['<user>'] or self.get_lastfm_nick(mask)
        user = mask.nick
        try:
            result = self.app.user.get_recent_tracks(
                lastfm_user,
                limit=1,
                extended=True)
        except (lastfm.exceptions.InvalidParameters,
                lastfm.exceptions.OperationFailed) as e:
            self.log.exception("Operation failed when fetching recent tracks")
            return "{user}: Error: {message}".format(user=user, message=e)
        except:
            self.log.exception("Fatal exception when calling last.fm")
            return "{user}: Fatal exception occurred. Aborting.".format(
                user=user)
        else:
            response = ["{user}".format(user=user)]

            # Append 'on lastfm' to differentiate between !np lastfmnick and
            # !np someone_else_in_channel. The latter we don't and won't do.
            if args['<user>']:
                response.append('({nick} on Last.FM)'.format(nick=lastfm_user))

            # Empty result
            if 'track' not in result:
                response.append("is someone who never scrobbled before")
            else:
                track = result['track']
                # The API might return a list. Strip it off.
                if isinstance(track, list):
                    track = result['track'][0]
                info = _parse_trackinfo(track)

                time_ago = datetime.datetime.utcnow() - info['playtime']
                if time_ago.days > 0 or time_ago.seconds > (20*60):
                    response.append('is not currently playing anything '
                                    '(last seen {time} ago).'.format(
                                        time=_time_ago(info['playtime'])))

                    return ' '.join(response)

                self.fetch_extra_trackinfo(lastfm_user, info)

                if info['now playing']:
                    response.append('is now playing')
                else:
                    response.append('was just playing')

                response.append('“{artist} – {title}”'.format(
                    artist=info['artist'],
                    title=info['title']))

                if info['loved']:
                    response.append('(♥)')

                if info.get('playcount', 0) > 0:
                    if info['playcount'] == 1:
                        response.append('(1 play)')
                    else:
                        response.append('({} plays)'.format(info['playcount']))

                if not info['now playing']:
                    minutes = time_ago.seconds // 60
                    seconds = time_ago.seconds % 60
                    if minutes > 0:
                        response.append("({}m{:02}s ago)".format(minutes,
                                                                 seconds))
                    else:
                        response.append("({}s ago)".format(seconds))

            return ' '.join(response) + '.'

    def get_lastfm_nick(self, mask):
        """Gets the last.fm nick associated with a user from the database
        """
        QUERY = "SELECT lastfmuser FROM lastfm WHERE userid = ?"
        cursor = self.bot.get_database().get_cursor()
        userid = self.bot.get_user(mask.nick).getid()
        cursor.execute(QUERY, [userid])
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return mask.nick

    def _init_database(self):
        QUERY = ("CREATE TABLE lastfm ("
                 "lastfmuser VARCHAR(50) NOT NULL,"
                 "userid VARCHAR(80) NOT NULL,"
                 "PRIMARY KEY (userid) )")

        self.bot.get_database().execute_and_commit_query(QUERY)

    def fetch_extra_trackinfo(self, username, info):
        """Updates info with extra trackinfo from the last.fm API"""
        try:
            if 'mbid' in info:
                api_result = self.app.track.get_info(mbid=info['mbid'],
                                                     username=username)
            else:
                api_result = self.app.track.get_info(track=info['title'],
                                                     artist=info['artist'],
                                                     username=username)
        except lastfm.exceptions.InvalidParameters:
            return

        if 'userplaycount' in api_result:
            info['playcount'] = int(api_result['userplaycount'])

        if 'toptags' in api_result and 'tag' in api_result['toptags']:
            taglist = api_result['toptags']['tag']
            info['tags'] = [tag['name'] for tag in taglist]

        if 'userloved' in api_result and not info['loved']:
            info['loved'] = bool(int(api_result['userloved']))


def _time_ago(time):
    """Represent time past as a friendly string"""
    time_ago = datetime.datetime.utcnow() - time
    timestr = []
    if time_ago.days > 1:
        timestr.append("{} days".format(time_ago.days))
    elif time_ago.days == 1:
        timestr.append("1 day")

    # hours
    hours = time_ago.seconds//(60*60)
    if hours > 1:
        timestr.append("{} hours".format(hours))
    elif hours == 1:
        timestr.append("1 hour")

    # minutes
    minutes = time_ago.seconds % (60*60)//60
    if minutes > 1:
        timestr.append("{} minutes".format(minutes))
    elif minutes == 1:
        timestr.append("1 minute")

    return ', '.join(timestr)


def _parse_trackinfo(track):
    """Parses the track info into something more comprehensible"""
    now_playing = False
    if '@attr' in track and 'nowplaying' in track['@attr']:
        now_playing = bool(track['@attr']['nowplaying'])
        playtime = datetime.datetime.utcnow()
    else:
        playtime = datetime.datetime.utcfromtimestamp(
            int(track['date']['uts']))

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
