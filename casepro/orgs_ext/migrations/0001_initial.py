# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0014_auto_20150722_1419'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrgTaskState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('task_key', models.CharField(max_length=32)),
                ('last_run_on', models.DateTimeField(null=True)),
                ('last_results', models.TextField()),
                ('last_time_taken', models.IntegerField(null=True)),
                ('failing', models.BooleanField(default=False)),
                ('org', models.ForeignKey(related_name='task_states', to='orgs.Org')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='orgtaskstate',
            unique_together=set([('org', 'task_key')]),
        ),
    ]
