# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0009_partner_logo")]

    operations = [
        migrations.AlterField(
            model_name="partner",
            name="logo",
            field=models.ImageField(upload_to="partner_logos", null=True, verbose_name="Logo"),
        )
    ]
