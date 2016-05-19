# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0043_outgoing_reply_to'),
    ]

    operations = [
        migrations.AlterField(
            model_name='outgoing',
            name='created_on',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
