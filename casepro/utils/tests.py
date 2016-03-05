# coding=utf-8
from __future__ import unicode_literals

import pytz

from casepro.test import BaseCasesTest
from datetime import date, datetime
from . import safe_max, normalize, match_keywords, truncate, str_to_bool, is_dict_equal
from . import datetime_to_microseconds, microseconds_to_datetime


class UtilsTest(BaseCasesTest):

    def test_safe_max(self):
        self.assertEqual(safe_max(1, 2, 3), 3)
        self.assertEqual(safe_max(None, 2, None), 2)
        self.assertEqual(safe_max(None, None), None)
        self.assertEqual(safe_max(date(2012, 3, 6), date(2012, 5, 2), None), date(2012, 5, 2))

    def test_normalize(self):
        self.assertEqual(normalize("Mary  had\ta little lamb"), "mary had a little lamb")  # remove multiple spaces
        self.assertEqual(normalize("Gar\u00e7on"), "garc\u0327on")  # decomposed combined unicode chars (U+E7 = ç)

    def test_match_keywords(self):
        text = "Mary had a little lamb"
        self.assertFalse(match_keywords(text, []))
        self.assertFalse(match_keywords(text, ['sheep']))
        self.assertFalse(match_keywords(text, ['lambburger']))  # complete word matches only

        self.assertTrue(match_keywords(text, ['mary']))  # case-insensitive and start of string
        self.assertTrue(match_keywords(text, ['lamb']))  # end of string
        self.assertTrue(match_keywords(text, ['big', 'little']))  # one match, one mis-match
        self.assertTrue(match_keywords(text, ['little lamb']))  # spaces ok

    def test_truncate(self):
        self.assertEqual(truncate("Hello World", 8), "Hello...")
        self.assertEqual(truncate("Hello World", 8, suffix="_"), "Hello W_")
        self.assertEqual(truncate("Hello World", 98), "Hello World")

    def test_str_to_bool(self):
        self.assertFalse(str_to_bool("0"))
        self.assertFalse(str_to_bool("fALSe"))
        self.assertFalse(str_to_bool("N"))
        self.assertFalse(str_to_bool("No"))
        self.assertFalse(str_to_bool("x"))

        self.assertTrue(str_to_bool("1"))
        self.assertTrue(str_to_bool("TrUE"))
        self.assertTrue(str_to_bool("Y"))
        self.assertTrue(str_to_bool("YeS"))

    def test_microseconds_to_datetime(self):
        d1 = datetime(2015, 10, 9, 14, 48, 30, 123456, tzinfo=pytz.utc).astimezone(pytz.timezone("Africa/Kigali"))
        ms = datetime_to_microseconds(d1)
        d2 = microseconds_to_datetime(ms)
        self.assertEqual(d2, datetime(2015, 10, 9, 14, 48, 30, 123456, tzinfo=pytz.utc))

    def test_is_dict_equal(self):
        self.assertTrue(is_dict_equal({'a': 1, 'b': 2}, {'b': 2, 'a': 1}))
        self.assertFalse(is_dict_equal({'a': 1, 'b': 2}, {'a': 1, 'b': 3}))
        self.assertFalse(is_dict_equal({'a': 1, 'b': 2}, {'a': 1, 'c': 2}))
        self.assertFalse(is_dict_equal({'a': 1, 'b': 2}, {'a': 1, 'b': 2, 'c': 3}))

        self.assertTrue(is_dict_equal({'a': 1, 'b': 2, 'c': 3}, {'a': 1, 'b': 2, 'c': 4}, keys=('a', 'b')))

        self.assertTrue(is_dict_equal({'a': 1, 'b': 2}, {'a': 1, 'b': 2, 'c': None}, ignore_none_values=True))
        self.assertFalse(is_dict_equal({'a': 1, 'b': 2}, {'a': 1, 'b': 2, 'c': None}, ignore_none_values=False))
