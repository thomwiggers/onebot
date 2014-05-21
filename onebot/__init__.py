#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Thom Wiggers'
__email__ = 'thom@thomwiggers.nl'
__version__ = '0.1.0'

import irc3

import logging

class OneBot(irc3.IrcBot):
    """
    Main class, extensions of IrcBot
    """

    def __init__(self, *args, **kwargs):
        self.defaults['nick'] = 'OneBot'
        self.defaults['realname'] = 'OneBot'
        self.defaults['userinfo'] = 'IRC bot in python'
        self.defaults['cmdchar'] = '.'
        self.defaults['url'] = 'https://github.com/thomwiggers/OneBot/'
        self.defaults['ctcp']['version'] = 'OneBot {version}'
        self.defaults['version'] = __version__
        super(OneBot, self).__init__(*args, **kwargs)
