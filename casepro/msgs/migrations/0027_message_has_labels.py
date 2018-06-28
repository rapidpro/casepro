# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def populate_has_labels(apps, schema_editor):
    Org = apps.get_model("orgs", "Org")

    for org in Org.objects.order_by("pk"):
        print("Updating labels for org #%d..." % org.pk)

        for label in org.labels.all():
            print(" > Updating messages for label %s..." % label.name)
            label.messages.update(has_labels=True)


class Migration(migrations.Migration):

    dependencies = [("msgs", "0026_auto_20160309_1337")]

    operations = [
        migrations.AddField(model_name="message", name="has_labels", field=models.BooleanField(default=False)),
        migrations.RunPython(populate_has_labels),
    ]
