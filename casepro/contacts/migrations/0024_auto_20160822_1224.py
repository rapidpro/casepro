# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0023_contact_urns'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contact',
            name='uuid',
            field=models.CharField(max_length=36, unique=True, null=True),
        ),
    ]
