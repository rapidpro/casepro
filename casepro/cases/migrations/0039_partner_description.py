# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0038_partner_timezone'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='description',
            field=models.CharField(max_length=255, null=True, verbose_name='Description', blank=True),
        ),
    ]
