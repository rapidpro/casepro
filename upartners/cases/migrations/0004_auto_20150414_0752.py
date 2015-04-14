# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0003_auto_20150413_1140'),
    ]

    operations = [
        migrations.AlterField(
            model_name='case',
            name='message_id',
            field=models.IntegerField(unique=True),
            preserve_default=True,
        ),
    ]
