# -*- coding: utf8 -*-
"""
==============================================
:mod:`onebot.plugins.database` Database plugin
==============================================

Database provider for OneBot

Usage::

    >>> from irc3.testing import IrcBot
    >>> bot = IrcBot(database=':memory:')
    >>> bot.include('onebot.plugins.database')

Doing queries::

    >>> db = bot.get_database()
    >>> db.get_cursor()  # doctest: +ELLIPSIS
    <sqlite3.Cursor object at 0x...>
    >>> db.get_connection()  # doctest: +ELLIPSIS
    <sqlite3.Connection object at 0x...>
    >>> db.execute_and_commit_query("CREATE TABLE people (name)")

`execute_and_commit()` returns the new row id of the created row when
INSERTing::

    >>> db.execute_and_commit_query("INSERT INTO people VALUES ('bob')")
    1
    >>> db.get_cursor().execute("SELECT * FROM people").fetchone() == ('bob',)
"""
from __future__ import unicode_literals, print_function

import logging
import os
import sqlite3

import irc3


@irc3.plugin
class DatabasePlugin(object):
    """Database connection plugin for OneBot

    Extends OneBot with `get_database()` so you can get easy access to
    a database.
    """

    def __init__(self, bot, database=None):
        self.bot = bot
        self.log = logging.getLogger(__name__)
        dbpath = database or os.path.expanduser(
            bot.config.get('database', '~/.onebot/database.db'))

        self.log.info("Connecting to sqlite3 database %s", dbpath)
        self.connection = sqlite3.connect(dbpath)

    def get_cursor(self):
        """Return a database cursor to perform queries on.

        ..
            >>> from irc3.testing import IrcBot
            >>> bot = IrcBot(database=':memory:')
            >>> bot.include('onebot.plugins.database')
            >>> db = bot.get_database()

        Usage::

            >>> db.get_cursor()  # doctest: +ELLIPSIS
            <sqlite3.Cursor object at 0x...>

        """
        return self.connection.cursor()

    def get_connection(self):
        """Return the database connection

        ..
            >>> from irc3.testing import IrcBot
            >>> bot = IrcBot(database=':memory:')
            >>> bot.include('onebot.plugins.database')
            >>> db = bot.get_database()

        Usage::

            >>> db.get_connection()  # doctest: +ELLIPSIS
            <sqlite3.Connection object at 0x...>

        """
        return self.connection

    def execute_and_commit_query(self, query, *args):
        """Execute the query and commit it.

        Params:
            query
            list of arguments to substitute in query

        ..
            >>> from irc3.testing import IrcBot
            >>> bot = IrcBot(database=':memory:')
            >>> bot.include('onebot.plugins.database')
            >>> db = bot.get_database()

        Usage::

            >>> db.execute_and_commit_query("CREATE TABLE robots (name)")
            >>> # No result because there's no lastrowid
            >>> db.execute_and_commit_query("INSERT INTO robots "
            ...                             "VALUES ('Marvin')")
            1

        Returns the last row id when available (i.e. when query is
        an INSERT query).
        """
        self.log.debug("Executing query '%s' with arguments %s",
                       query, args)
        cursor = self.connection.execute(query, *args)

        # Return last row id when available
        # It's usually available on an insert query
        if cursor.lastrowid:
            return cursor.lastrowid

        self.connection.commit()

    @irc3.extend
    def get_database(self):
        """Get the `Database` object.
        ..
            >>> from irc3.testing import IrcBot
            >>> bot = IrcBot(database=':memory:')
            >>> bot.include('onebot.plugins.database')
            >>> db = bot.get_database()

        Usage::
            >>> bot.get_database()  # doctest: +ELLIPSIS
            <onebot.plugins.database.Database object at 0x...>
        """
        return self
