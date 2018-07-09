# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0038_no_empty_messages")]

    operations = [migrations.AlterField(model_name="outgoing", name="text", field=models.TextField(max_length=640))]
