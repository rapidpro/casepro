# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0011_auto_20150513_1542")]

    operations = [
        migrations.AddField(
            model_name="label", name="uuid", field=models.CharField(max_length=36, unique=True, null=True)
        )
    ]
