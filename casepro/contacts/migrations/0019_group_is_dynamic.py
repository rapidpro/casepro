# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0018_contact_is_blocked")]

    operations = [
        migrations.AddField(
            model_name="group",
            name="is_dynamic",
            field=models.BooleanField(default=False, help_text="Whether this group is dynamic"),
        )
    ]
