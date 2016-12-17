#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_onebot
----------------------------------

Tests for `onebot` module.
"""

from unittest import TestCase

from onebot import OneBot


class TestOnebot(TestCase):

    def setUp(self):
        self.bot = OneBot(testing=True, locale='en_US.UTF-8')

    def test_init(self):
        pass

    def tearDown(self):
        pass


if __name__ == '__main__':
    import unittest
    unittest.main()
