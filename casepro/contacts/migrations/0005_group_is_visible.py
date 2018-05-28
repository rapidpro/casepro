# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0004_group_count")]

    operations = [
        migrations.AddField(
            model_name="group",
            name="is_visible",
            field=models.BooleanField(default=False, help_text="Whether this group is visible to partner users"),
        )
    ]
