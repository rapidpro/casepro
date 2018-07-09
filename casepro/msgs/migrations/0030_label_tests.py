# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import json

from django.db import migrations, models

from casepro.rules.models import ContainsTest, Quantifier
from casepro.utils import parse_csv


def populate_label_tests(apps, schema_editor):
    Label = apps.get_model("msgs", "Label")

    for label in Label.objects.all():
        keywords = parse_csv(label.keywords) if label.keywords else []

        if keywords:
            label.tests = json.dumps([ContainsTest(keywords, Quantifier.ANY).to_json()])
            label.save(update_fields=("tests",))

            print("Migrated label #%d with keywords %s" % (label.pk, label.keywords))


class Migration(migrations.Migration):

    dependencies = [("msgs", "0029_folder_indexes_pt3")]

    operations = [
        migrations.AddField(model_name="label", name="tests", field=models.TextField(blank=True)),
        migrations.RunPython(populate_label_tests),
    ]
