# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0002_auto_20160208_1517")]

    operations = [
        migrations.AlterField(
            model_name="field",
            name="value_type",
            field=models.CharField(default="T", max_length=1, verbose_name="Value data type"),
        )
    ]
