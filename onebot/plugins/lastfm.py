# -*- coding: utf8 -*-
"""
======================================================
:mod:`onebot.plugins.lastfm` Last.FM plugin for OneBot
======================================================

..
    >>> import tempfile
    >>> fd = tempfile.NamedTemporaryFile(prefix='irc3', suffix='.json')
    >>> json_file = fd.name
    >>> fd.close()

Usage::

    >>> from irc3.testing import IrcBot, patch
    >>> bot = IrcBot(**{
    ...     'onebot.plugins.lastfm': {'api_key': 'foo',
    ...                               'api_secret': 'bar'},
    ...     'cmd': '!',
    ...     'storage': 'json://%(json_file)s' % {'json_file' : json_file}
    ... })
    >>> bot.include('onebot.plugins.lastfm')

"""
import asyncio
from datetime import datetime

import irc3
import lastfm.exceptions
from musicbrainzngs import get_artist_by_id
from operator import itemgetter
from irc3.plugins.command import command
from lastfm import lfm


@irc3.plugin
class LastfmPlugin(object):
    """Plugin to provide:

    * now playing functionality
    """

    requires = [
        'irc3.plugins.command',
        'onebot.plugins.users'
    ]

    def __init__(self, bot):
        """Initialise the plugin"""
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        self.config = bot.config.get(__name__, {})
        musicbrainzngs.set_useragent(__name__, 1.0)
        try:
            self.app = lfm.App(self.config['api_key'], self.config[
                               'api_secret'], self.config.get('cache_file'))
        except KeyError:  # pragma: no cover
            raise Exception(
                "You need to set the Last.FM api_key and api_scret "
                "in the config section [{}]".format(__name__))

    @command
    def np(self, mask, target, args):
        """Show currently playing track

            %%np [<user>]
        """
        if target == self.bot.nick:
            target = mask.nick

        @asyncio.coroutine
        def wrap():
            response = yield from self.now_playing_response(mask, args)
            self.log.debug(response)
            self.bot.privmsg(target, response)
        asyncio.async(wrap())

    @command
    def setuser(self, mask, target, args):
        """Sets the lastfm username of the user

            %%setuser <lastfmnick>
        """
        self.log.info("Storing lastfmuser %s for %s",
                      args['<lastfmnick>'], mask.nick)
        self.bot.get_user(mask.nick).set_setting(
            'lastfmuser', args['<lastfmnick>'])
        self.bot.privmsg(
            target, 'Ok, so you are https://last.fm/user/{username}'.format(username=args['<lastfmnick>']))

    @command
    def ignoreme(self, mask, target, args):
        """Sets that the user wants to be excluded from %%compare

            %%ignoreme
        """
        self.log.info("Excluding %s from .compare", mask.nick)
        self.bot.get_user(mask.nick).set_setting('nocompare', True)
        self.bot.privmsg(
            target, ("I will leave out {nick} from compare. Re-enable compare by using the unignoreme command").format(nick=mask.nick))

    @command
    def unignoreme(self, mask, target, args):
        """Sets that the user wants to be included again in %%compare

            %%unignoreme
        """
        self.log.info("Including %s in .compare", mask.nick)
        self.bot.get_user(mask.nick).set_setting('nocompare', False)
        self.bot.privmsg(
            target, "Ok, enabled compare for {user}".format(user=mask.nick))

    @asyncio.coroutine
    def now_playing_response(self, mask, args):
        """Return appropriate response to np request"""
        lastfm_user = args['<user>']
        if not lastfm_user:
            lastfm_user = yield from self.get_lastfm_nick(mask.nick)
        user = mask.nick

        try:
            result = self.app.user.get_recent_tracks(
                lastfm_user, limit=1, extended=True)
        except (lastfm.exceptions.InvalidParameters,
                lastfm.exceptions.OperationFailed,
                lastfm.exceptions.AuthenticationFailed) as e:
            errmsg = str(e)
            # filter out common failure and show status
            if errmsg == "No user with that name was found":
                errmsg = "No Last.fm user found for {username}".format(
                    username=user)
            else:
                self.log.exception(
                    "Operation failed when fetching recent tracks", exc_info=e)

            if (lastfm_user != user and lastfm_user in errmsg):  # pragma: no cover
                errmsg = "(Error message withheld)"
                self.log.critical("Error message contained user name!")

            reponse = "{user}: Error: {message}".format(
                user=user, message=errmsg)
            return response

        except Exception as e:  # pragma: no cover
            self.log.exception(
                "Fatal exception when calling last.fm", exc_info=e)
            reponse = (
                "{user}: Fatal exception occurred. Aborting. Check http://status.last.fm".format(user=user))
            return reponse

        response = ["{user}".format(user=user)]

        # Append 'on lastfm' to differentiate between !np lastfmnick and
        # !np someone_else_in_channel. The latter we don't and won't do.
        if args['<user>']:
            response.append('({nick} on Last.FM)'.format(nick=lastfm_user))

        # Empty result
        if 'track' not in result or (isinstance(result['track'], list) and len(result['track']) == 0):
            response.append("is someone who never scrobbled before")
            return ' '.join(response) + '.'

        # The API might return a list. Strip it off.
        track = result['track'][0] if isinstance(
            track, list) else result['track']

        info = _parse_trackinfo(track)

        time_ago = datetime.utcnow() - info['playtime']
        if time_ago.days > 0 or time_ago.seconds > (20 * 60):
            response.append('is not currently playing anything (last seen {time} ago)'.format(
                time=_time_ago(info['playtime'])))
            return ' '.join(response) + '.'

        # No more special cases
        self.fetch_extra_trackinfo(lastfm_user, info)

        if info['now playing']:
            response.append('is now playing')
        else:
            response.append('was just playing')

        response.append('“{artist} – {title}”'.format(**info))

        if info['loved']:
            response.append('(♥)')

        if info.get('playcount', 0) > 0:
            if info['playcount'] == 1:  # pragma: no cover
                response.append('(1 play)')
            else:
                response.append('({playcount} plays)'.format(**info))

        if not info['now playing']:
            minutes = time_ago.seconds // 60
            seconds = time_ago.seconds % 60
            if minutes > 0:
                response.append("({}m{:02}s ago)".format(minutes, seconds))
            else:  # pragma: no cover
                response.append("({}s ago)".format(seconds))

        if 'tags' in info and len(info['tags']) > 0:
            response.append(
                '({})'.format(', '.join(info['tags'][:4])))

        return ' '.join(response) + '.'

    @asyncio.coroutine
    def get_lastfm_nick(self, nick):
        """Gets the last.fm nick associated with a user from the database
        """
        user = self.bot.get_user(nick)
        if user:
            result = yield from user.get_setting('lastfmuser', nick)
            return result
        else:  # pragma: no cover
            return nick

    def fetch_extra_trackinfo(self, username, info):
        """Updates info with extra trackinfo from the last.fm API"""
        try:
            extra_info = self.app.track.get_info(track=info['title'], artist=info[
                                                 'artist'], username=username)
        except lastfm.exceptions.InvalidParameters:
            self.log.warning(
                "Last.fm returned InvalidParameters for trackinfo")
            return
        except:
            self.log.exception("Got a random for trackinfo")
            return

        if 'userplaycount' in extra_info:
            info['playcount'] = int(extra_info['userplaycount'])

        if 'mbid' in info:
            mb = get_artist_by_id(info['mbid'], includes='tags')
            sorted_tags = sorted(mb['artist']['tag-list'],
                                 key=itemgetter('count'), reverse=True)

            tags = []
            for tag in sorted_tags:
                tags.append(tag['name'])
            info['tags'] = tags

        if 'userloved' in extra_info and not info['loved']:
            info['loved'] = bool(int(extra_info['userloved']))

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)


def _time_ago(time):
    """Represent time past as a friendly string"""
    time_ago = datetime.utcnow() - time
    timestr = []
    if time_ago.days > 1:
        timestr.append("{} days".format(time_ago.days))
    elif time_ago.days == 1:
        timestr.append("1 day")

    # hours
    hours = time_ago.seconds // (60 * 60)
    if hours > 1:
        timestr.append("{} hours".format(hours))
    elif hours == 1:
        timestr.append("1 hour")

    # minutes
    minutes = time_ago.seconds % (60 * 60) // 60
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
        playtime = datetime.utcnow()
    else:
        playtime = datetime.utcfromtimestamp(int(track['date']['uts']))

    loved = False
    loved = bool(int(track['loved'])) if 'loved' in track:

    result = {
        'title': track['name'],
        'artist': track['artist']['name'],
        'album': track['album']['#text'],
        'now playing': now_playing,
        'loved': loved,
        'playtime': playtime
    }

    result['mbid'] = track['mbid'] if 'mbid' in track['artist']

    return result
