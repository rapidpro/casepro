import calendar
import iso639
import json
import pytz
import re
import unicodedata

from dateutil.relativedelta import relativedelta
from datetime import datetime, time, timedelta
from django.utils.timesince import timeuntil
from django.utils import timezone
from enum import Enum
from temba_client.utils import format_iso8601
from uuid import UUID


LANGUAGES_BY_CODE = {}  # cache of language lookups


def parse_csv(csv, as_ints=False):
    """
    Parses a comma separated list of values as strings or integers
    """
    items = []
    for val in csv.split(","):
        val = val.strip()
        if val:
            items.append(int(val) if as_ints else val)
    return items


def str_to_bool(text):
    """
    Parses a boolean value from the given text
    """
    return text and text.lower() in ["true", "y", "yes", "1"]


class JSONEncoder(json.JSONEncoder):
    """
    JSON encoder which encodes datetime values as strings
    """

    def default(self, val):
        if isinstance(val, datetime):
            return format_iso8601(val)
        elif isinstance(val, Enum):
            return val.name
        elif hasattr(val, "to_json") and callable(val.to_json):
            return val.to_json()

        return json.JSONEncoder.default(self, val)  # pragma: no cover


def json_encode(data):
    """
    Encodes the given primitives as JSON using Django's encoder which can handle dates
    """
    return json.dumps(data, cls=JSONEncoder)


def json_decode(data):
    """
    Decodes the given JSON as primitives
    """
    if isinstance(data, bytes):
        data = data.decode("utf-8")

    return json.loads(data)


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
    return unicodedata.normalize("NFKD", re.sub(r"\s+", " ", text.lower()))


def match_keywords(text, keywords):
    """
    Checks the given text for a keyword match
    """
    for keyword in keywords:
        if re.search(r"\b" + keyword + r"\b", text, flags=re.IGNORECASE):
            return True
    return False


def truncate(text, length=100, suffix="..."):
    """
    Truncates the given text to be no longer than the given length
    """
    if len(text) > length:
        return text[: length - len(suffix)] + suffix
    else:
        return text


def date_to_milliseconds(d):
    """
    Converts a date to a millisecond accuracy timestamp. Equivalent to Date.UTC(d.year, d.month-1, d.day) in Javascript
    """
    return calendar.timegm(datetime.combine(d, time(0, 0, 0)).replace(tzinfo=pytz.UTC).utctimetuple()) * 1000


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
    return datetime.utcfromtimestamp(ms / 1000000.0).replace(tzinfo=pytz.utc)


def month_range(offset, now=None):
    """
    Gets the UTC start and end (exclusive) of a month
    :param offset: 0 = this month, -1 last month, 1 = next month etc
    :return: the start and end datetimes as a tuple
    """
    if not now:
        now = timezone.now()

    now = now.astimezone(pytz.UTC)
    start_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return start_of_this_month + relativedelta(months=offset), start_of_this_month + relativedelta(months=offset + 1)


def date_range(start, stop):
    """
    A date-based range generator
    """
    for n in range(int((stop - start).days)):
        yield start + timedelta(n)


class TimelineItem(object):
    """
    Wraps a message or action for easier inclusion in a merged timeline
    """

    def __init__(self, item):
        self.item = item

    def get_time(self):
        return self.item.created_on

    def to_json(self):
        return {"time": self.get_time(), "type": self.item.TIMELINE_TYPE, "item": self.item.as_json()}


def uuid_to_int(uuid):
    """
    Converts a UUID hex string to an int within the range of a Django IntegerField, and also >=0, as the URL regexes
    don't account for negative numbers.

    From https://docs.djangoproject.com/en/1.9/ref/models/fields/#integerfield
    "Values from -2147483648 to 2147483647 are safe in all databases supported by Django"
    """
    return UUID(hex=uuid).int % (2147483647 + 1)


def get_language_name(iso_code):
    """
    Gets the language name for the given ISO639-3 code.
    """
    if iso_code not in LANGUAGES_BY_CODE:
        try:
            lang = iso639.languages.get(part3=iso_code)
        except KeyError:
            lang = None

        if lang:
            # we only show up to the first semi or paren
            lang = re.split(";|\(", lang.name)[0].strip()

        LANGUAGES_BY_CODE[iso_code] = lang

    return LANGUAGES_BY_CODE[iso_code]


def is_valid_language_code(code):
    """
    Gets whether the given code is a valid ISO639-3 code.
    """
    try:
        iso639.languages.get(part3=code)
        return True
    except KeyError:
        return False


def humanize_seconds(seconds):
    now = timezone.now()
    return timeuntil(now + timedelta(seconds=seconds), now)
