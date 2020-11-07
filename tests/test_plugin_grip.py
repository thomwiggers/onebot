#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_plugin_psa
----------------------------------

Tests for PSA module
"""

from datetime import date
from unittest import TestCase

from freezegun import freeze_time

from onebot.plugins import grip


# this is a saturday
@freeze_time("2020-11-07")
class DateParserTest(TestCase):
    """Test some dates"""

    def test_dateparser(self):
        tomorrow = date(2020, 11, 8)
        self.assertEqual(grip.parse_date("tomorrow"), tomorrow)
        self.assertEqual(grip.parse_date("morgen"), tomorrow)
        self.assertEqual(grip.parse_date("sunday"), tomorrow)
        self.assertEqual(grip.parse_date("zondag"), tomorrow)
        self.assertEqual(grip.parse_date("dinsdag"), date(2020, 11, 10))

        with self.assertRaises(ValueError):
            grip.parse_date("astrnoarshoiaershto")
