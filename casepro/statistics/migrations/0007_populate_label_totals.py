# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def populate_label_totals(apps, schema_editor):
    Label = apps.get_model("msgs", "Label")
    TotalCount = apps.get_model("statistics", "TotalCount")

    labels = list(Label.objects.all())

    for num, label in enumerate(labels):
        inbox_count = label.messages.filter(is_archived=False, is_handled=True, is_active=True).count()
        archived_count = label.messages.filter(is_archived=True, is_handled=True, is_active=True).count()

        TotalCount.objects.create(item_type="N", scope="label:%d" % label.pk, count=inbox_count)
        TotalCount.objects.create(item_type="A", scope="label:%d" % label.pk, count=archived_count)

        print("Calculated total counts for %d of %d labels" % (num, len(labels)))


class Migration(migrations.Migration):

    dependencies = [("statistics", "0006_totalcount")]

    operations = [migrations.RunPython(populate_label_totals)]
