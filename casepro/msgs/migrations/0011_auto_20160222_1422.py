# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0010_label_migrate_pt4")]

    operations = [
        migrations.AlterField(
            model_name="label",
            name="description",
            field=models.CharField(max_length=255, null=True, verbose_name="Description"),
        ),
        migrations.AlterField(
            model_name="label",
            name="keywords",
            field=models.CharField(max_length=1024, null=True, verbose_name="Keywords", blank=True),
        ),
    ]
