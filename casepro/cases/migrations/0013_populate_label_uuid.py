# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations


def get_or_create_remote(org, name):
    client = org.get_temba_client()
    temba_labels = client.get_labels(name=name)  # gets all partial name matches
    temba_labels = [l for l in temba_labels if l.name.lower() == name.lower()]

    if temba_labels:
        return temba_labels[0]
    else:
        return client.create_label(name)


def fetch_label_uuids(apps, schema_editor):
    Label = apps.get_model("cases", "Label")

    labels = list(Label.objects.filter(uuid=None).select_related("org"))
    for label in labels:
        remote = get_or_create_remote(label.org, label.name)
        label.uuid = remote.uuid
        label.save(update_fields=("uuid",))

    if labels:
        print("Fetched missing UUIDs for %d labels" % len(labels))


class Migration(migrations.Migration):

    dependencies = [("cases", "0012_label_uuid"), ("orgs", "0014_auto_20150722_1419")]

    operations = [migrations.RunPython(fetch_label_uuids)]
