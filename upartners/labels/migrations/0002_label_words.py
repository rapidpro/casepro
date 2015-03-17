# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('labels', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='label',
            name='words',
            field=models.CharField(default='', max_length=1024, verbose_name='Match words'),
            preserve_default=False,
        ),
    ]
