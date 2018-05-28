# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0031_remove_label_keywords")]

    operations = [
        migrations.AddField(
            model_name="label",
            name="is_synced",
            field=models.BooleanField(default=True, help_text="Whether this label should be synced with the backend"),
        )
    ]
