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
            name='is_active',
            field=models.BooleanField(default=True, help_text='Whether this label is active'),
            preserve_default=True,
        ),
    ]
