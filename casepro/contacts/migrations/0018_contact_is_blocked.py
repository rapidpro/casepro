# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0017_remove_value_model")]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="is_blocked",
            field=models.BooleanField(default=False, help_text="Whether this contact is blocked"),
        )
    ]
