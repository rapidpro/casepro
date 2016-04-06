from __future__ import unicode_literals

import calendar
import datetime
import json
import pytz
import re
import unicodedata

from enum import Enum
from temba_client.utils import format_iso8601


def parse_csv(csv, as_ints=False):
    """
    Parses a comma separated list of values as strings or integers
    """
    items = []
    for val in csv.split(','):
        val = val.strip()
        if val:
            items.append(int(val) if as_ints else val)
    return items


def str_to_bool(text):
    """
    Parses a boolean value from the given text
    """
    return text and text.lower() in ['true', 'y', 'yes', '1']


def json_encode(data):
    """
    Encodes the given primitives as JSON using Django's encoder which can handle dates
    """
    return json.dumps(data, cls=JSONEncoder)


def safe_max(*args, **kwargs):
    """
    Regular max won't compare dates with NoneType and raises exception for no args
    """
    non_nones = [v for v in args if v is not None]
    if len(non_nones) == 0:
        return None
    elif len(non_nones) == 1:
        return non_nones[0]
    else:
        return max(*non_nones, **kwargs)


def normalize(text):
    """
    Normalizes text before keyword matching. Converts to lowercase, performs KD unicode normalization and replaces
    multiple whitespace characters with single spaces.
    """
    return unicodedata.normalize('NFKD', re.sub(r'\s+', ' ', text.lower()))


def match_keywords(text, keywords):
    """
    Checks the given text for a keyword match
    """
    for keyword in keywords:
        if re.search(r'\b' + keyword + r'\b', text, flags=re.IGNORECASE):
            return True
    return False


def truncate(text, length=100, suffix='...'):
    """
    Truncates the given text to be no longer than the given length
    """
    if len(text) > length:
        return text[:length-len(suffix)] + suffix
    else:
        return text


class JSONEncoder(json.JSONEncoder):
    """
    JsON encoder which encodes datetime values as strings
    """
    def default(self, val):
        if isinstance(val, datetime.datetime):
            return format_iso8601(val)
        elif isinstance(val, Enum):
            return val.name
        elif hasattr(val, 'to_json') and callable(val.to_json):
            val = val.to_json()

        return json.JSONEncoder.default(self, val)


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
