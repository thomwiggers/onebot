# -*- coding: utf8 -*-
"""
======================================================
:mod:`onebot.plugins.wolframalpha` WolframAlpha queries
======================================================

Usage::

    >>> from irc3.testing import IrcBot, patch
    >>> bot = IrcBot(**{
    ...     'onebot.plugins.wolframalpha': {
    ...         'appid': '12AB34-12345689XA'
    ...     },
    ...     'cmd': '!',
    ... })
    >>> bot.include('onebot.plugins.trakt')

"""
import irc3
from irc3.plugins.command import command

import requests


WOLFRAM_API_URL = 'https://api.wolframalpha.com/v1/result'


@irc3.plugin
class WolframAlphaPlugin(object):
    """Plugin to provide:

    * Wolfram Alpha queries from IRC
    """

    requires = [
        'irc3.plugins.command',
    ]

    def __init__(self, bot):
        """Initialise the plugin"""
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        self.config = bot.config.get(__name__, {})
        self.appid = self.config['appid']

    @command
    def wa(self, mask, target, args):
        """Queries the Wolfram|Alpha engine

            %%wa <query>...
        """
        try:
            response = requests.get(
                WOLFRAM_API_URL,
                params={
                    'appid': self.appid,
                    'i': ' '.join(args['<query>'])
                })
            response.raise_for_status()
            return f"{mask.nick}: {response.text}"
        except requests.exceptions.HTTPError as exception:
            return f"HTTP error: '{exception}'"
        except requests.exceptions.Timeout:
            return "Request timed out"
        except requests.exceptions.RequestException as exception:
            return f"Request failed: '{exception}'"

    @classmethod
    def reload(cls, old):  # pragma: no cover
        """Reload this module"""
        return cls(old.bot)
