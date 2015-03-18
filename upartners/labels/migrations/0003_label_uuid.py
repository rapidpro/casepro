# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('labels', '0002_label_words'),
    ]

    operations = [
        migrations.AddField(
            model_name='label',
            name='uuid',
            field=models.CharField(max_length=36, null=True),
            preserve_default=True,
        ),
    ]
