# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0023_label_migrate_pt2")]

    operations = [
        migrations.RemoveField(model_name="case", name="labels"),
        migrations.RemoveField(model_name="caseaction", name="label"),
        migrations.RemoveField(model_name="label", name="partners"),
    ]
