# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0026_auto_20160222_1203")]

    operations = [
        migrations.AlterField(
            model_name="partner",
            name="labels",
            field=models.ManyToManyField(
                help_text="Labels that this partner can access",
                related_name="partners",
                verbose_name="Labels",
                to="msgs.Label",
            ),
        )
    ]
