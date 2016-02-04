# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orgs_ext', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='taskstate',
            old_name='results',
            new_name='last_results',
        ),
        migrations.AddField(
            model_name='taskstate',
            name='last_successfully_started_on',
            field=models.DateTimeField(null=True),
        ),
    ]
