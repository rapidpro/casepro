# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0050_label_watchers'),
    ]

    operations = [
        migrations.CreateModel(
            name='LabelCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('archived_count', models.IntegerField()),
                ('inbox_count', models.IntegerField()),
                ('label', models.ForeignKey(to='msgs.Label')),
            ],
        ),
    ]
