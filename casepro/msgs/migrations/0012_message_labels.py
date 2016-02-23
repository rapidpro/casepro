# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0011_auto_20160222_1422'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='labels',
            field=models.ManyToManyField(help_text='Labels assigned to this message', to='msgs.Label'),
        ),
    ]
