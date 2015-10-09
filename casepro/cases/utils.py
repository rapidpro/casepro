from __future__ import absolute_import, unicode_literals

import calendar
import datetime
import pytz


def datetime_to_microseconds(dt):
    """
    Converts a datetime to a microsecond accuracy timestamp
    """
    seconds = calendar.timegm(dt.utctimetuple())
    return seconds * 1000000 + dt.microsecond


def microseconds_to_datetime(ms):
    """
    Converts a microsecond accuracy timestamp to a datetime
    """
    return datetime.datetime.utcfromtimestamp(ms / 1000000.0).replace(tzinfo=pytz.utc)
