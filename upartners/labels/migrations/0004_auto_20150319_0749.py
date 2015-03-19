# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('labels', '0003_label_uuid'),
    ]

    operations = [
        migrations.RenameField(
            model_name='label',
            old_name='words',
            new_name='keywords',
        ),
        migrations.AlterField(
            model_name='label',
            name='keywords',
            field=models.CharField(max_length=1024, verbose_name='Keywords', blank=True),
            preserve_default=True,
        ),
    ]
