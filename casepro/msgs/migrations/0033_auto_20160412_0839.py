# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0032_label_is_synced")]

    operations = [
        migrations.AlterField(
            model_name="label", name="uuid", field=models.CharField(max_length=36, unique=True, null=True)
        )
    ]
