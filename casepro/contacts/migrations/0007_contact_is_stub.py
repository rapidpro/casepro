# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0006_migrate_filter_groups")]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="is_stub",
            field=models.BooleanField(default=False, help_text="Whether this contact is just a stub"),
        )
    ]
