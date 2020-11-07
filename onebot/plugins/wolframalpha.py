# -*- coding: utf8 -*-
"""
======================================================
:mod:`onebot.plugins.wolframalpha` WolframAlpha queries
======================================================

Usage::

    >>> from onebot.testing import IrcBot, patch
    >>> bot = IrcBot(**{
    ...     'onebot.plugins.wolframalpha': {
    ...         'appid': '12AB34-12345689XA'
    ...     },
    ...     'cmd': '!',
    ... })
    >>> bot.include('onebot.plugins.wolframalpha')

"""
import urllib.parse

import irc3
from irc3.plugins.command import command

import requests


WOLFRAM_API_URL = "https://api.wolframalpha.com/v1/result"


@irc3.plugin
class WolframAlphaPlugin(object):
    """Plugin to provide:

    * Wolfram Alpha queries from IRC
    """

    requires = [
        "irc3.plugins.command",
    ]

    def __init__(self, bot):
        """Initialise the plugin"""
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        self.config = bot.config.get(__name__, {})
        self.appid = self.config["appid"]

    @command
    def wa(self, mask, target, args):
        """Queries the Wolfram|Alpha engine

        %%wa <query>...
        """
        question = " ".join(args["<query>"])
        self.log.info("Got Wolfram|Alpha question '%s'", question)
        try:
            response = requests.get(
                WOLFRAM_API_URL,
                params={
                    "appid": self.appid,
                    "i": question,
                    "units": "metric",
                },
            )
            response.raise_for_status()
            return f"{mask.nick}: {response.text}"
        except requests.exceptions.HTTPError:
            if response.status_code == 501:
                self.log.info("no short answer for '%s'", question)
                return (
                    "No short answer available. See "
                    "https://www.wolframalpha.com/input/?i="
                    f"{urllib.parse.quote(question)}"
                )

            self.log.exception("HTTP error for question: '%s'", question)
            return f"HTTP error {response.status_code}"
        except requests.exceptions.Timeout:
            self.log.error("Request timed out")
            return "Request timed out"
        except requests.exceptions.RequestException:
            self.log.error(f"Request '{question}' failed")
            return f"Request failed"

    @classmethod
    def reload(cls, old):  # pragma: no cover
        """Reload this module"""
        return cls(old.bot)
