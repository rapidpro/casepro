# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0025_label_migrate_pt5")]

    operations = [
        migrations.AlterField(
            model_name="case",
            name="labels",
            field=models.ManyToManyField(help_text="Labels assigned to this case", to="msgs.Label"),
        ),
        migrations.AlterField(
            model_name="partner",
            name="labels",
            field=models.ManyToManyField(
                help_text="Labels that this partner can access", to="msgs.Label", verbose_name="Labels"
            ),
        ),
    ]
