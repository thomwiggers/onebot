"""
================================================
:mod:`onebot.plugins.stonks` 
================================================

This plugin allows to query stonks
"""

import requests
import urllib.parse

import irc3
from irc3.plugins.command import command

import logging

logger = logging.getLogger(__name__)


@irc3.plugin
class StonksPlugin(object):
    """Stonks Plugin"""

    requires = [
        "irc3.plugins.command",
    ]

    def __init__(self, bot):
        """Initialise the plugin"""
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        self.config = bot.config.get(__name__, {})
        self.api_key_iex = self.config["api_key_iex"]

    def lookup(self, symbol):
      try:
        api_key = self.api_key_iex
        response = requests.get(f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}")
        print(response)
        response.raise_for_status()
      except requests.RequestException:
        print(2)
        return None

      try:
        quote = response.json()
        return {
              "name": quote["companyName"],
              "price": float(quote["latestPrice"]),
              "symbol": quote["symbol"]
            }
      except (KeyError, TypeError, ValueError):
        return None

    @command
    def stonk(self, _mask, _target, args):
        """Check the value of your stonks.

        %%stonk <symbol>
        """
        result = self.lookup(args["<symbol>"])
        if result != None:
          resultString = f"Name: {result['name']}, Price: {result['price']}, Symbol: {result['symbol']}"
          return resultString
        else:
          return "Invalid"

