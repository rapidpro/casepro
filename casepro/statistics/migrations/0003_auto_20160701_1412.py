# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("statistics", "0002_populate_reply_counts")]

    operations = [migrations.AlterField(model_name="dailycount", name="count", field=models.IntegerField())]
