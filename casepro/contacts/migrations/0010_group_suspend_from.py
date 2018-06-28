# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0009_contact_suspended_groups")]

    operations = [
        migrations.AddField(
            model_name="group",
            name="suspend_from",
            field=models.BooleanField(
                default=False, help_text="Whether contacts should be suspended from this group during a case"
            ),
        )
    ]
