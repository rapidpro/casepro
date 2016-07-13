# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def populate_label_counts(apps, schema_editor):
    Label = apps.get_model('msgs', 'Label')
    LabelCount = apps.get_model('msgs', 'LabelCount')

    labels = list(Label.objects.all())

    for num, label in enumerate(labels):
        inbox_count = label.messages.filter(is_archived=False, is_handled=True, is_active=True).count()
        archived_count = label.messages.filter(is_archived=True, is_handled=True, is_active=True).count()

        LabelCount.objects.create(label=label, inbox_count=inbox_count, archived_count=archived_count)

        print("Pre-calculated counts for %d of %d labels" % (num, len(labels)))


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0051_labelcount'),
    ]

    operations = [
        migrations.RunPython(populate_label_counts)
    ]
