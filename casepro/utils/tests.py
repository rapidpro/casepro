# coding=utf-8
from __future__ import unicode_literals

import hypothesis.strategies as st
import pytz

from datetime import date, datetime
from django.core import mail
from django.http import HttpRequest
from django.test import override_settings
from enum import Enum
from hypothesis import given
from uuid import UUID

from casepro.test import BaseCasesTest

from . import safe_max, normalize, match_keywords, truncate, str_to_bool, json_encode, TimelineItem, uuid_to_int
from . import date_to_milliseconds, datetime_to_microseconds, microseconds_to_datetime, month_range, date_range
from . import get_language_name, is_valid_language_code, json_decode, humanize_seconds
from .email import send_email
from .middleware import JSONMiddleware


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

    def test_date_to_milliseconds(self):
        self.assertEqual(date_to_milliseconds(date(2015, 1, 1)), 1420070400000)
        self.assertEqual(date_to_milliseconds(date(2015, 2, 1)), 1422748800000)

    def test_microseconds_to_datetime(self):
        d1 = datetime(2015, 10, 9, 14, 48, 30, 123456, tzinfo=pytz.utc).astimezone(pytz.timezone("Africa/Kigali"))
        ms = datetime_to_microseconds(d1)
        d2 = microseconds_to_datetime(ms)
        self.assertEqual(d2, datetime(2015, 10, 9, 14, 48, 30, 123456, tzinfo=pytz.utc))

    def test_json_encode(self):
        class MyEnum(Enum):
            bar = 1

        class MyClass(object):
            def to_json(self):
                return dict(bar='X')

        data = [
            "string",
            datetime(2015, 10, 9, 14, 48, 30, 123456, tzinfo=pytz.utc).astimezone(pytz.timezone("Africa/Kigali")),
            MyEnum.bar,
            MyClass()
        ]

        self.assertEqual(json_encode(data), '["string", "2015-10-09T14:48:30.123456Z", "bar", {"bar": "X"}]')
        self.assertEqual(json_encode({'foo': "bar\u1234"}), '{"foo": "bar\\u1234"}')

    def json_decode(self):
        self.assertEqual(json_decode('{"foo":"bar\\u1234"}'), {'foo': "bar\u1234"})
        self.assertEqual(json_decode('{"foo":"bar\u1234"}'), {'foo': "bar\u1234"})
        self.assertEqual(json_decode(b'{"foo":"bar\u1234"}'), {'foo': "bar\u1234"})

    def test_month_range(self):
        d1 = datetime(2015, 10, 9, 14, 48, 30, 123456, tzinfo=pytz.utc).astimezone(pytz.timezone("Africa/Kigali"))

        self.assertEqual(month_range(0, now=d1), (datetime(2015, 10, 1, 0, 0, 0, 0, pytz.UTC),
                                                  datetime(2015, 11, 1, 0, 0, 0, 0, pytz.UTC)))
        self.assertEqual(month_range(1, now=d1), (datetime(2015, 11, 1, 0, 0, 0, 0, pytz.UTC),
                                                  datetime(2015, 12, 1, 0, 0, 0, 0, pytz.UTC)))
        self.assertEqual(month_range(-1, now=d1), (datetime(2015, 9, 1, 0, 0, 0, 0, pytz.UTC),
                                                   datetime(2015, 10, 1, 0, 0, 0, 0, pytz.UTC)))

    def test_date_range(self):
        self.assertEqual(list(date_range(date(2015, 1, 29), date(2015, 2, 2))), [
            date(2015, 1, 29),
            date(2015, 1, 30),
            date(2015, 1, 31),
            date(2015, 2, 1)
        ])
        self.assertEqual(list(date_range(date(2015, 1, 29), date(2015, 1, 29))), [])

    def test_timeline_item(self):
        d1 = datetime(2015, 10, 1, 9, 0, 0, 0, pytz.UTC)
        ann = self.create_contact(self.unicef, 'C-101', "Ann")
        msg = self.create_message(self.unicef, 102, ann, "Hello", created_on=d1)
        self.assertEqual(TimelineItem(msg).to_json(), {'time': d1, 'type': 'I', 'item': msg.as_json()})

    def test_uuid_to_int_range(self):
        """
        Ensures that the integer returned will always be in the range [0, 2147483647].
        """
        self.assertEqual(uuid_to_int(UUID(int=(2147483647)).hex), 2147483647)
        self.assertEqual(uuid_to_int(UUID(int=(2147483648)).hex), 0)

    @given(st.uuids())
    def test_uuid_to_int_property(self, uuid):
        """
        Property based testing to ensure that the output of the function is always within the limits.
        """
        self.assertTrue(uuid_to_int(uuid.hex) <= 2147483647)
        self.assertTrue(uuid_to_int(uuid.hex) >= 0)

    def test_get_language_name(self):
        self.assertEqual(get_language_name('fra'), "French")
        self.assertEqual(get_language_name('fra'), "French")  # from cache
        self.assertEqual(get_language_name('pcm'), "Nigerian Pidgin")

        # should strip off anything after an open paren or semicolon
        self.assertEqual(get_language_name('arc'), "Official Aramaic")

        self.assertIsNone(get_language_name('xxxxx'))

    def test_is_valid_language_code(self):
        self.assertTrue(is_valid_language_code('fra'))
        self.assertFalse(is_valid_language_code('fre'))  # old ISO639-2 code

    def test_humanize_seconds(self):
        self.assertEqual(humanize_seconds(59), u"0\xa0minutes")
        self.assertEqual(humanize_seconds(119), u"1\xa0minute")
        self.assertEqual(humanize_seconds(120), u"2\xa0minutes")
        self.assertEqual(humanize_seconds(3600), u"1\xa0hour")
        self.assertEqual(humanize_seconds(7200), u"2\xa0hours")
        self.assertEqual(humanize_seconds(3719), u"1\xa0hour, 1\xa0minute")
        self.assertEqual(humanize_seconds(3720), u"1\xa0hour, 2\xa0minutes")
        self.assertEqual(humanize_seconds(7319), u"2\xa0hours, 1\xa0minute")
        self.assertEqual(humanize_seconds(7320), u"2\xa0hours, 2\xa0minutes")
        self.assertEqual(humanize_seconds(86400), "1\xa0day")
        self.assertEqual(humanize_seconds(172800), "2\xa0days")
        self.assertEqual(humanize_seconds(93599), "1\xa0day, 1\xa0hour")
        self.assertEqual(humanize_seconds(93600), "1\xa0day, 2\xa0hours")
        self.assertEqual(humanize_seconds(180000), "2\xa0days, 2\xa0hours")


class EmailTest(BaseCasesTest):
    @override_settings(SEND_EMAILS=True)
    def test_send_email(self):
        send_email([self.user1, 'bob@unicef.org'], "Subject", 'utils/email/export',
                   {'download_url': 'http://example.com/export/1/'})

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["evan@unicef.org"])
        self.assertEqual(mail.outbox[0].subject, "Subject")
        self.assertEqual(mail.outbox[1].to, ["bob@unicef.org"])


class MiddlewareTest(BaseCasesTest):
    def test_json(self):
        middleware = JSONMiddleware()

        # test with no content type header
        request = HttpRequest()
        request._body = '{"a":["b"]}'
        middleware.process_request(request)
        self.assertFalse(hasattr(request, 'json'))

        # test with JSON content type header
        request = HttpRequest()
        request._body = '{"a":["b"]}'
        request.META = {'CONTENT_TYPE': "application/json;charset=UTF-8"}
        middleware.process_request(request)
        self.assertEqual(request.json, {'a': ["b"]})

        # test with non-JSON content type header
        request = HttpRequest()
        request._body = '<b></b>'
        request.META = {'CONTENT_TYPE': "text/html"}
        middleware.process_request(request)
        self.assertFalse(hasattr(request, 'json'))


class ViewsTest(BaseCasesTest):
    def test_partials(self):
        response = self.url_get('unicef', '/partials/modal_confirm.html')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "[[ title ]]")
