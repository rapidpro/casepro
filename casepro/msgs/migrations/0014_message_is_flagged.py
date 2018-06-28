# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0013_auto_20160223_0917")]

    operations = [
        migrations.AddField(model_name="message", name="is_flagged", field=models.BooleanField(default=False))
    ]
