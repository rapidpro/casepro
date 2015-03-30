# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('labels', '0004_auto_20150319_0749'),
        ('cases', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='labels',
            field=models.ManyToManyField(related_name='cases', verbose_name='Labels', to='labels.Label'),
            preserve_default=True,
        ),
    ]
