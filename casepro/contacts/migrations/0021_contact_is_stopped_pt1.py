# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0020_unset_suspend_from_dynamic")]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="is_stopped",
            field=models.NullBooleanField(help_text="Whether this contact opted out of receiving messages"),
        ),
        migrations.AlterField(
            model_name="contact",
            name="is_stopped",
            field=models.NullBooleanField(
                default=False, help_text="Whether this contact opted out of receiving messages"
            ),
        ),
    ]
