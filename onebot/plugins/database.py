# -*- coding: utf8 -*-
"""
===============================================
:mod:`onebot.plugins.database` NoSQL data store
===============================================

Provides a NoSQL datastore for OneBot

Usage::

    >>> from irc3.testing import IrcBot
    >>> bot = IrcBot()
    >>> bot.include('onebot.plugins.database')  # doctest: +SKIP

Doing queries::

    >>> db = bot.get_database()  # get collection  # doctest: +SKIP
    >>> db.save({"x": 10})  # doctest: +SKIP
    ObjectId(...)
    >>> db.fetch_one()  # doctest: +SKIP
    {'x': 10, '_id': ObjectId('...')
"""
from __future__ import unicode_literals, print_function

import logging

import pymongo
import irc3


@irc3.plugin
class DatabasePlugin(object):
    """MongoDB Database connection plugin for OneBot

    Extends OneBot with `get_database()` so you can get easy access to
    a database.
    """

    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger(__name__)
        self.config = bot.config.get(__name__, {})
        host = self.config.get('host', 'localhost')
        port = self.config.get('port', 27017)
        database = bot.config.get('database', 'onebot')

        self.log.info("Connecting to MongoDB database %s on $s:%d",
                      database, host, port)
        client = pymongo.MongoClient(host, port)
        self.connection = client[database]

    def get_connection(self):
        """Return the database connection

        Usage::

            >>> db.get_connection()  # doctest: +SKIP
            MongoClient('localhost', 27017)
        """
        return self.connection

    @irc3.extend
    def get_database(self):
        """Get the MongoDB ``client`` object.

        Usage::

            >>> bot.get_database()  # doctest: +SKIP
            <onebot.plugins.database.DatabasePlugin object at 0x...>
        """
        return self

    def __getattr__(self, name):
        return self.connection.__getattr__(name)
