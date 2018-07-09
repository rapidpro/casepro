# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0003_auto_20160209_1048")]

    operations = [migrations.AddField(model_name="group", name="count", field=models.IntegerField(null=True))]
