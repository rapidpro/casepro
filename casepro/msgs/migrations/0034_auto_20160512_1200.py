# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0020_unset_suspend_from_dynamic"), ("msgs", "0033_auto_20160412_0839")]

    operations = [
        migrations.AddField(
            model_name="outgoing",
            name="contacts",
            field=models.ManyToManyField(related_name="outgoing_messages", to="contacts.Contact"),
        ),
        migrations.AddField(
            model_name="outgoing",
            name="urns",
            field=django.contrib.postgres.fields.ArrayField(
                default=list, base_field=models.CharField(max_length=255), size=None
            ),
        ),
        migrations.AlterField(
            model_name="outgoing",
            name="backend_id",
            field=models.IntegerField(help_text="Broadcast id from the backend", unique=True, null=True),
        ),
    ]
