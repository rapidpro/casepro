# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0050_label_watchers")]

    operations = [
        migrations.AlterField(
            model_name="label",
            name="name",
            field=models.CharField(help_text="Name of this label", max_length=64, verbose_name="Name"),
        )
    ]
