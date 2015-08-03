# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from casepro.cases.models import Label
from django.db import migrations


def fetch_label_uuids(apps, schema_editor):
    labels = list(Label.objects.filter(uuid=None).select_related('org'))
    for label in labels:
        remote = Label.get_or_create_remote(label.org, label.name)
        label.uuid = remote.uuid
        label.save(update_fields=('uuid',))

    if labels:
        print "Fetched missing UUIDs for %d labels" % len(labels)


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0012_label_uuid'),
        ('orgs', '0014_auto_20150722_1419'),
    ]

    operations = [
        migrations.RunPython(fetch_label_uuids)
    ]
