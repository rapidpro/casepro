# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0022_contact_is_stopped_pt2")]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="urns",
            field=django.contrib.postgres.fields.ArrayField(
                default=list,
                help_text="List of URNs of the format 'scheme:path'",
                base_field=models.CharField(max_length=255),
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="contact", name="uuid", field=models.CharField(max_length=36, unique=True, null=True)
        ),
    ]
