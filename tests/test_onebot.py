#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_onebot
----------------------------------

Tests for `onebot` module.
"""

import asyncio
from unittest import TestCase

from onebot import OneBot


class TestOnebot(TestCase):
    def setUp(self):
        self.bot = OneBot(testing=True, asynchronous=False, locale="en_US.UTF-8")

    def test_init(self):
        pass

    def tearDown(self):
        loop = self.bot.loop
        if isinstance(loop, asyncio.AbstractEventLoop) and not loop.is_closed():
            loop.close()


if __name__ == "__main__":
    import unittest

    unittest.main()
