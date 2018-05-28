# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0020_auto_20160303_1058")]

    operations = [migrations.AlterField(model_name="outgoing", name="created_on", field=models.DateTimeField())]
