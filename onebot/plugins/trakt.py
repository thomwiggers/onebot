# -*- coding: utf8 -*-
"""
======================================================
:mod:`onebot.plugins.trakt` Trakt.TV plugin for OneBot
======================================================

..
    >>> import tempfile
    >>> fd = tempfile.NamedTemporaryFile(prefix='irc3', suffix='.json')
    >>> json_file = fd.name
    >>> fd.close()

Usage::

    >>> from irc3.testing import IrcBot, patch
    >>> bot = IrcBot(**{
    ...     'onebot.plugins.trakt': {'client_id': 'foo',
    ...                              'api_secret': 'bar'},
    ...     'cmd': '!',
    ...     'storage': 'json://%(json_file)s' % {'json_file' : json_file}
    ... })
    >>> bot.include('onebot.plugins.trakt')

"""
import asyncio

import irc3
from irc3.plugins.command import command

import requests


@irc3.plugin
class TrakttvPlugin(object):
    """Plugin to provide:

    * now watching functionality
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
        self.client_id = self.config['client_id']

    @command
    def nw(self, mask, target, args):
        """Shows what you are currently watching via Trakt.tv

            %%nw [<user>]
        """
        if target == self.bot.nick:
            target = mask.nick

        @asyncio.coroutine
        def wrap():
            response = yield from self.now_watching_response(mask, args)
            self.log.debug(response)
            self.bot.privmsg(target, response)
        asyncio.async(wrap())

    @command
    def settraktuser(self, mask, target, args):
        """Sets the trakttv username of the user

            %%settraktuser <trakttvnick>
        """
        self.log.info("Storing trakt user %s for %s",
                      args['<trakttvnick>'], mask.nick)
        self.bot.get_user(mask.nick).set_setting(
            'trakttvnick', args['<trakttvnick>'])
        self.bot.privmsg(
            target,
            'Ok, so you are https://trakt.tv/users/{username}'.format(
                username=args['<trakttvnick>']))

    @asyncio.coroutine
    def now_watching_response(self, mask, args):
        """Return appropriate response to np request"""
        trakt_user = args['<user>']
        if not trakt_user:
            trakt_user = yield from self.get_trakt_nick(mask.nick)
        user = mask.nick

        request = requests.get(
            'https://api.trakt.tv/users/{}/watching'.format(
                trakt_user),
            headers={
                'Content-Type': 'application/json',
                'trakt-api-version': '2',
                'trakt-api-key': self.client_id})
        response = [user]
        if args['<user>']:
            response.append('({} on Trakt.tv)'.format(trakt_user))
        if request.status_code == 204:
            response.append("You're not playing anything")
        elif request.status_code == 200:
            try:
                data = request.json()
                response.append('is now watching')
                if data['type'] == 'episode':
                    response.append(data['show']['title'])
                    response.append('—')
                    response.append('S{:02}E{:02}'.format(
                        data['episode']['season'],
                        data['episode']['number']))
                    response.append('—')
                    response.append(data['episode']['title'])
                elif data['type'] == 'movie':
                    response.append(data['movie']['title'])
                    response.append('({})'.format(data['movie']['year']))
                else:
                    response.append("something I don't understand")
            except (ValueError, KeyError):
                return 'Something went wrong'
        else:
            response.append(
                'Something went wrong. '
                'Is your account set to private? '
                'Status code: {}'.format(request.status_code))
        return ' '.join(response)

    @asyncio.coroutine
    def get_trakt_nick(self, nick):
        """Gets the trakt.tv nick associated with a user from the database
        """
        user = self.bot.get_user(nick)
        if user:
            result = yield from user.get_setting('trakttvnick', nick)
            return result
        else:  # pragma: no cover
            return nick

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
