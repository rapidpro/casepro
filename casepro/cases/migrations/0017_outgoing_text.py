# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0016_case_contact")]

    operations = [
        migrations.AddField(model_name="outgoing", name="text", field=models.TextField(max_length=640, null=True))
    ]
