# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0025_auto_20160309_1336")]

    operations = [
        migrations.AlterField(
            model_name="outgoing",
            name="backend_id",
            field=models.IntegerField(help_text="Broadcast id from the backend", unique=True),
        )
    ]
