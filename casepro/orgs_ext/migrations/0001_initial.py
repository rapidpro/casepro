# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0014_auto_20150722_1419'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('task_key', models.CharField(max_length=32)),
                ('started_on', models.DateTimeField(null=True)),
                ('ended_on', models.DateTimeField(null=True)),
                ('results', models.TextField(null=True)),
                ('is_failing', models.BooleanField(default=False)),
                ('org', models.ForeignKey(related_name='task_states', to='orgs.Org')),
            ],
            options={
                'db_table': 'orgs_taskstate',
            },
        ),
        migrations.AlterUniqueTogether(
            name='taskstate',
            unique_together=set([('org', 'task_key')]),
        ),
    ]
