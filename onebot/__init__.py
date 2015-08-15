#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Main onebot class and the command line runner"""
import locale

import irc3


__author__ = 'Thom Wiggers'
__email__ = 'thom@thomwiggers.nl'
__version__ = '0.1.0'


class OneBot(irc3.IrcBot):
    """Main class, extensions of IrcBot"""

    def __init__(self, *args, **kwargs):
        self.defaults['nick'] = 'OneBot'
        self.defaults['realname'] = 'OneBot'
        self.defaults['userinfo'] = 'IRC bot in python'
        self.defaults['cmdchar'] = '.'
        self.defaults['url'] = 'https://github.com/thomwiggers/OneBot/'
        self.defaults['ctcp']['version'] = 'OneBot {version}'
        self.defaults['version'] = __version__

        if 'locale' in kwargs:
            locale.setlocale(locale.LC_ALL, kwargs['locale'])

        super(OneBot, self).__init__(*args, **kwargs)


def run(argv=None):  # pragma: no cover
    """Run OneBot from a config file

    Usage: onebot [options] <config>...

    Options::

        --logdir DIRECTORY  Log directory to use instead of stderr
        --logdate           Show datetimes in console output
        -r,--raw            Show raw IRC log on the console
        -v,--verbose        Increase verbosity
        -d,--debug          Add debug commands/utils
    """
    import sys
    import docopt
    import textwrap
    import os
    from irc3 import utils, config
    args = argv or sys.argv[1:]
    args = docopt.docopt(textwrap.dedent(run.__doc__), args)
    cfg = utils.parse_config('bot', *args['<config>'])
    cfg.update(
        verbose=args['--verbose'],
        debug=args['--debug'])

    if args['--logdir'] or 'logdir' in cfg:
        logdir = os.path.expanduser(args['--logdir'] or cfg.get('logdir'))
        OneBot.logging_config = config.get_file_config(logdir)

    bot = OneBot.from_config(cfg)

    bot.run()

    if argv:
        return bot
