# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0011_migrate_suspend_groups")]

    operations = [
        migrations.AddField(
            model_name="field",
            name="is_visible",
            field=models.BooleanField(default=False, help_text="Whether this field is visible to partner users"),
        )
    ]
