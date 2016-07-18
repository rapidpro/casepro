# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0037_partner_is_restricted'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='timezone',
            field=models.CharField(default='UTC', help_text='The timezone the partner organization is in.', max_length=64, verbose_name='Timezone'),
        ),
    ]
