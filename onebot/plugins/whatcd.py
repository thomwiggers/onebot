# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.whatcd` WhatCD wiki plugin
================================================

This plugin allows to easily link the wiki.
"""

from datetime import datetime
from urllib.parse import quote_plus

from irc3 import plugin
from irc3.plugins.command import command

WIKI_SEARCH_URL = 'https://what.cd/wiki.php?action=search&search={terms}'


@plugin
class WhatCDPlugin(object):
    """What.CD plugin"""

    requires = [
        'irc3.plugins.storage',
    ]

    def __init__(self, bot):
        """Init"""
        self.bot = bot
        self.config = bot.config.get(__name__, {})
        self.log = self.bot.log.getChild(__name__)

    @command
    def wiki(self, mask, target, args):
        """Link to a wiki search or article

            %%wiki <terms>...
        """
        wikikey = 'wiki{}'.format(''.join(args['<terms>'])).lower()
        if wikikey in self.bot.db:
            yield self.bot.db[wikikey]['response']
            return
        yield WIKI_SEARCH_URL.format(
            terms=quote_plus(' '.join(args['<terms>'])))

    @command(permission='wiki')
    def wikialias(self, mask, target, args):
        """Teach the bot to reply a certian wiki url.

            %%wikialias <terms> <response>...

        terms needs to have no whitespace. For '!wiki', 'a b' == 'ab'.
        response may contain spaces and text.
        """
        self.bot.db['wiki{}'.format(args['<terms>'].lower())] = {
            'by': str(mask),
            'channel': target,
            'date': str(datetime.utcnow()),
            'response': ' '.join(args['<response>'])}
        yield "Registered"

    @command(permission='wiki')
    def wikidelete(self, mask, target, args):
        """Delete a wiki key

            %%wikidelete <terms>
        """
        try:
            del self.bot.db['wiki{}'.format(args['<terms>'].lower())]
            yield "Deleted"
        except KeyError:
            yield "Key does not exist"

    @command(permission='wiki', show_in_help_list=False)
    def wikiinfo(self, mask, target, args):
        """Get information on a wiki alias

            %%wikiinfo <terms>...
        """
        wikikey = 'wiki{}'.format(''.join(args['<terms>'])).lower()
        if wikikey in self.bot.db:
            entry = self.bot.db[wikikey]
            yield ('Key {key} registered by {user} in {channel} '
                   'on {date} (UTC)'.format(key=wikikey[4:],
                                            user=entry['by'],
                                            channel=entry['channel'],
                                            date=entry['date']))
            yield 'Response: {}'.format(entry['response'])
        else:
            yield 'No such alias found, so falls back to search.'

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
