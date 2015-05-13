from __future__ import absolute_import, unicode_literals

import json
import re

from django.core.serializers.json import DjangoJSONEncoder


MAX_MESSAGE_CHARS = 140
SYSTEM_LABEL_FLAGGED = "Flagged"
LABEL_KEYWORD_MIN_LENGTH = 3


def str_to_bool(text):
    """
    Parses a boolean value from the given text
    """
    return text and text.lower() in ['true', 'y', 'yes', '1']


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


def json_encode(data):
    return json.dumps(data, cls=DjangoJSONEncoder)


def contact_as_json(contact, field_keys):
    """
    Prepares a contact (fetched from RapidPro) for JSON serialization
    """
    return {'uuid': contact.uuid,
            'fields': {key: contact.fields.get(key, None) for key in field_keys}}


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
