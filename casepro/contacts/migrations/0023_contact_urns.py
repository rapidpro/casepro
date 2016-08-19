# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0022_contact_is_stopped_pt2'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='urns',
            field=django.contrib.postgres.fields.ArrayField(default=list, help_text="List of URNs of the format 'scheme:urn'", base_field=models.CharField(max_length=128), size=None),
        ),
    ]
