# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0024_auto_20160822_1224'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contact',
            name='urns',
            field=django.contrib.postgres.fields.ArrayField(default=list, help_text="List of URNs of the format 'scheme:path'", base_field=models.CharField(max_length=255), size=None),
        ),
    ]
