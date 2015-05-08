# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='summary',
            field=models.CharField(default='TEMP', max_length=255, verbose_name='Summary'),
            preserve_default=False,
        ),
    ]
