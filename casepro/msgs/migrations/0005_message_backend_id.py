# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0004_messageexport")]

    operations = [
        migrations.AddField(
            model_name="message",
            name="backend_id",
            field=models.IntegerField(default=1, help_text="Backend identifier for this message", unique=True),
            preserve_default=False,
        )
    ]
