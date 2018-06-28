# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0010_auto_20150512_1424")]

    operations = [
        migrations.AlterField(
            model_name="partner",
            name="logo",
            field=models.ImageField(upload_to="partner_logos", null=True, verbose_name="Logo", blank=True),
        )
    ]
