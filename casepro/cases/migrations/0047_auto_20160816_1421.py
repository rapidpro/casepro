# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0046_case_last_assignee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='case',
            name='initial_message',
            field=models.OneToOneField(related_name='initial_case', null=True, to='msgs.Message'),
        ),
    ]
