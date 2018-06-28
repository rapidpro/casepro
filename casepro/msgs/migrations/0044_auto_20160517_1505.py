# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0043_outgoing_reply_to")]

    operations = [
        migrations.AlterField(
            model_name="outgoing", name="created_on", field=models.DateTimeField(default=django.utils.timezone.now)
        )
    ]
