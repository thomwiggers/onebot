"""
================================================
:mod:`onebot.plugins.stonks` 
================================================

This plugin allows to query stonks
"""

import requests
import json
import re

import irc3
from irc3.plugins.command import command

import logging

from requests import exceptions

logger = logging.getLogger(__name__)


def stonks(symbol):
    headers = {"User-agent": "Mozilla/5.0"}
    url = f"https://finance.yahoo.com/quote/{symbol}?p={symbol}"
    response = requests.get(url, headers=headers)
    if response.status_code != requests.codes.ok:
        return "Error when fetching from Yahoo Finance"
    text = response.text

    # Look for begin and end of the JSON Blob
    json_start = re.search("root.App.main = ", text)
    json_end = re.search("}}}};", text)

    if json_start is None or json_end is None:
        return "Unexpected response from Yahoo Finance"

    # Cut down the text to only the JSON
    text_cut = text[json_start.span()[1] : json_end.span()[1] - 1]

    # Read the JSON and look for the preferred data
    try:
        data = json.loads(text_cut)
    except json.JSONDecodeError:
        return "Invalid JSON from Yahoo Finance"

    try:
        stock = data["context"]["dispatcher"]["stores"]["QuoteSummaryStore"]["price"]
    except KeyError:
        return "Symbol not found"

    if stock["regularMarketPrice"]["raw"] == 0:
        return "Symbol not found (perhaps try a variant symbol like .AS?)"

    if stock["regularMarketChangePercent"]["raw"] > 0.0:
        percentage = f"+{stock['regularMarketChangePercent']['fmt']}"
    else:
        percentage = stock["regularMarketChangePercent"]["fmt"]

    output = (
        f"{stock['shortName']}, "
        f"{stock['currencySymbol']}{stock['regularMarketPrice']['fmt']}, "
        f"{percentage}, "
        f"{stock['exchangeName']} ({stock['marketState']})"
    )
    return output


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

    @command
    def stonk(self, _mask, _target, args):
        """Check the value of your stonks.

        %%stonk <symbol>
        """
        symbol = args["<symbol>"]
        return stonks(symbol)

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
