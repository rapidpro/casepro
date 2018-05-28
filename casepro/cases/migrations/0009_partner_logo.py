# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0008_auto_20150510_1413")]

    operations = [
        migrations.AddField(
            model_name="partner", name="logo", field=models.ImageField(upload_to=b"", null=True, verbose_name="Logo")
        )
    ]
