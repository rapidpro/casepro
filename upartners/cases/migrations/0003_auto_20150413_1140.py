# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0002_case_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='message_id',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='case',
            name='message_on',
            field=models.DateTimeField(default=datetime.datetime(2015, 4, 13, 11, 40, 3, 925899, tzinfo=utc), help_text='When initial message was sent'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='case',
            name='contact_uuid',
            field=models.CharField(max_length=36, db_index=True),
            preserve_default=True,
        ),
        migrations.RenameField(
            model_name='case',
            old_name='partner',
            new_name='assignee',
        ),
        migrations.AlterField(
            model_name='caseaction',
            name='case',
            field=models.ForeignKey(related_name='actions', to='cases.Case'),
            preserve_default=True,
        ),
        migrations.RenameField(
            model_name='caseaction',
            old_name='performed_by',
            new_name='created_by',
        ),
        migrations.RenameField(
            model_name='caseaction',
            old_name='performed_on',
            new_name='created_on',
        ),
    ]
