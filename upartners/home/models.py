from __future__ import absolute_import, unicode_literals

import json

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _
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


class MessageExport(models.Model):
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='exports')

    search = models.TextField()

    filename = models.CharField(max_length=512)

    created_by = models.ForeignKey(User, related_name="exports")

    created_on = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create(cls, org, user, search):
        return MessageExport.objects.create(org=org, created_by=user, search=json.dumps(search))

    def get_search(self):
        return json.loads(self.search)
