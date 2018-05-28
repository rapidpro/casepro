# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="field",
            name="is_active",
            field=models.BooleanField(default=True, help_text="Whether this field is active"),
        ),
        migrations.AddField(
            model_name="field",
            name="value_type",
            field=models.CharField(default="T", max_length=1, verbose_name="Value data type"),
            preserve_default=False,
        ),
    ]
