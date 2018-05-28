# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from dash.utils import chunks
from django.db import migrations, models


def populate_is_stopped(apps, schema_editor):
    Contact = apps.get_model("contacts", "Contact")

    contact_ids = list(Contact.objects.values_list("id", flat=True))
    num_updated = 0

    for id_batch in chunks(contact_ids, 5000):
        Contact.objects.filter(pk__in=id_batch).update(is_stopped=False)
        num_updated += len(id_batch)

        print("Populated is_stopped for %d of %d contacts" % (num_updated, len(contact_ids)))


class Migration(migrations.Migration):

    dependencies = [("contacts", "0021_contact_is_stopped_pt1")]

    operations = [
        migrations.RunPython(populate_is_stopped),
        migrations.AlterField(
            model_name="contact",
            name="is_stopped",
            field=models.BooleanField(default=False, help_text="Whether this contact opted out of receiving messages"),
        ),
    ]
