# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0005_message_backend_id")]

    operations = [
        migrations.AddField(
            model_name="message", name="is_handled", field=models.BooleanField(default=True), preserve_default=False
        ),
        migrations.AlterField(model_name="message", name="is_handled", field=models.BooleanField(default=False)),
    ]
