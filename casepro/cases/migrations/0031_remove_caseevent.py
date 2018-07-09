# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0030_auto_20160303_1808")]

    operations = [
        migrations.RemoveField(model_name="caseevent", name="case"),
        migrations.DeleteModel(name="CaseEvent"),
    ]
