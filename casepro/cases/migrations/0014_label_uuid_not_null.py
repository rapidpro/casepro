# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0013_populate_label_uuid")]

    operations = [
        migrations.AlterField(model_name="label", name="uuid", field=models.CharField(unique=True, max_length=36))
    ]
