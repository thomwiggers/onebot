#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_onebot
----------------------------------

Tests for `onebot` module.
"""

from unittest import TestCase, mock

from onebot import OneBot


class TestOnebot(TestCase):

    def setUp(self):
        self.bot = OneBot(testing=True, locale='en_US.UTF-8')

    def test_init(self):
        pass

    @mock.patch('irc3.IrcBot.join')
    @mock.patch('onebot.OneBot.send')
    def test_join(self, mock2, mock1):
        self.bot.join('#ru')
        mock1.assert_called_with('#ru')
        mock2.assert_called_with('WHO #ru')

    def tearDown(self):
        pass

if __name__ == '__main__':
    import unittest
    unittest.main()
