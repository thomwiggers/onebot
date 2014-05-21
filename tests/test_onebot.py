#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_onebot
----------------------------------

Tests for `onebot` module.
"""

import unittest

from onebot import OneBot


class TestOnebot(unittest.TestCase):

    def setUp(self):
        self.bot = OneBot(testing=True)

    def test_init(self):
        pass

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
