# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0028_case_initial_message")]

    operations = [migrations.AlterField(model_name="case", name="message_id", field=models.IntegerField(null=True))]
