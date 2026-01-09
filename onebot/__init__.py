#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Main onebot class and the command line runner"""

import locale

import irc3


__author__ = "Thom Wiggers"
__email__ = "thom@thomwiggers.nl"
__version__ = "0.1.0"


class OneBot(irc3.IrcBot):
    """Main class, extensions of IrcBot"""

    def __init__(self, *args, **kwargs):
        self.defaults["nick"] = "OneBot"
        self.defaults["realname"] = "OneBot"
        self.defaults["userinfo"] = "IRC bot in python"
        self.defaults["cmdchar"] = "."
        self.defaults["url"] = "https://github.com/thomwiggers/OneBot/"
        self.defaults["ctcp"]["version"] = "OneBot {version}"  # type: ignore
        self.defaults["version"] = __version__

        if "locale" in kwargs:
            locale.setlocale(locale.LC_ALL, kwargs["locale"])

        super(OneBot, self).__init__(*args, **kwargs)


def run(argv=None):  # pragma: no cover
    """Run OneBot from a config file"""
    import sys
    import argparse
    import os
    from irc3 import utils, config

    parser = argparse.ArgumentParser(
        prog="onebot",
        description="Run OneBot from a config file",
    )
    parser.add_argument(
        "--logdir", metavar="DIRECTORY", help="Log directory to use instead of stderr"
    )
    parser.add_argument(
        "--logdate", action="store_true", help="Show datetimes in console output"
    )
    parser.add_argument(
        "-r", "--raw", action="store_true", help="Show raw IRC log on the console"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Increase verbosity"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Add debug commands/utils"
    )
    parser.add_argument("config", nargs="+", help="Config file(s)")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    cfg = utils.parse_config("bot", *args.config)
    cfg.update(verbose=args.verbose, debug=args.debug)

    if (logdir := (args.logdir or cfg.get("logdir"))) is not None:
        logdir = os.path.expanduser(logdir)
        OneBot.logging_config = config.get_file_config(logdir)

    bot = OneBot.from_config(cfg)

    bot.run()

    if argv:
        return bot
