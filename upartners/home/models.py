from __future__ import absolute_import, unicode_literals

from upartners.labels.models import SYSTEM_LABEL_FLAGGED


def parse_csv(csv, as_ints=False):
    """
    Parses a comma separated list of values as strings or integers
    """
    items = []
    for val in csv.split(','):
        if val:
            items.append(int(val) if as_ints else val.strip())
    return items


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
