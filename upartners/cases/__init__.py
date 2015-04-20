from __future__ import absolute_import, unicode_literals

import json

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


def json_encode(data):
    return json.dumps(data, cls=DjangoJSONEncoder)


def message_as_json(msg, label_map):
    """
    Prepares a message (fetched from RapidPro) for JSON serialization
    """
    flagged = SYSTEM_LABEL_FLAGGED in msg.labels

    # convert label names to JSON label objects
    labels = [label_map[label_name].as_json() for label_name in msg.labels if label_name in label_map]

    return {'id': msg.id,
            'text': msg.text,
            'contact': msg.contact,
            'urn': msg.urn,
            'time': msg.created_on,
            'labels': labels,
            'flagged': flagged,
            'direction': msg.direction}


def contact_as_json(contact, field_keys):
    """
    Prepares a contact (fetched from RapidPro) for JSON serialization
    """
    return {'uuid': contact.uuid,
            'fields': {key: contact.fields.get(key, None) for key in field_keys}}


def truncate(text, length=100, suffix='...'):
    if len(text) > length:
        return text[:length-len(suffix)] + suffix
    else:
        return text
