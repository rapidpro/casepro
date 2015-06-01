from __future__ import absolute_import, unicode_literals

import json
import unicodedata
import re

from django.core.serializers.json import DjangoJSONEncoder


MAX_MESSAGE_CHARS = 140
SYSTEM_LABEL_FLAGGED = "Flagged"


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
    return json.dumps(data, cls=DjangoJSONEncoder)


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
    Normalizes text before keyword matching. Converts to lowercase, performs KC unicode normalization and replaces
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
    if len(text) > length:
        return text[:length-len(suffix)] + suffix
    else:
        return text
