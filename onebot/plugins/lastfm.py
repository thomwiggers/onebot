"""
Last.FM plugin for OneBot

Author: Thom Wiggers
"""
from __future__ import unicode_literals, print_function

import irc3
from irc3.plugins.command import command

from lastfm import lfm
import lastfm.exceptions

import datetime

# TODO remove
import json


@irc3.plugin
class LastfmPlugin(object):
    """
    Plugin to provide:

    * now playing functionality
    * compare users' lastfm accounts through the tasteometer.
    """

    def __init__(self, bot):
        """
        TODO get key and secret from config
        """
        self.bot = bot
        self.config = bot.config.get(__name__, {})
        try:
            self.app = lfm.App(self.config['api_key'],
                               self.config['api_secret'],
                               self.config.get('cache_file'))
        except KeyError:
            raise Exception(
                "You need to set the Last.FM api_key and api_secret "
                "in the config section [{}]".format(__name__))

    @command
    def np(self, mask, target, args):
        """
        Show currently playing track

            %%np [<user>]
        """
        user = args['<user>'] or mask.nick
        try:
            result = self.app.user.get_recent_tracks(
                user,
                limit=1,
                extended=True)
        except lastfm.exceptions.InvalidParameters as e:
            print(e)
        except Exception as e:
            self.bot.log.exception(e)
            print("Random error")
        else:
            response = "{user}: ".format(user=user)
            print(result)
            if 'track' not in result:
                response += "found someone who never scrobbled before."
            else:
                track = result['track']
                # The API might return a list. Strip it off.
                if type(track) == list:
                    track = result['track'][0]
                print(json.dumps(track, indent=4))
                print(_parse_trackinfo(track))

            print(response)


def _parse_trackinfo(track):
    now_playing = False
    if '@attr' in track and 'nowplaying' in track['@attr']:
        now_playing = bool(track['@attr']['nowplaying'])

    loved = False
    if 'loved' in track:
        loved = bool(int(track['loved']))

    playtime = datetime.datetime.fromtimestamp(int(track['date']['uts']))

    return {'title': track['name'],
            'artist': track['artist']['name'],
            'now_playing': now_playing,
            'loved': loved,
            'playtime': playtime}
