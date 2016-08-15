# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0041_case_user_assignee'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseaction',
            name='user_assignee',
            field=models.ForeignKey(related_name='case_assigned_actions', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, help_text='The (optional) user that the case was assigned to.', null=True),
        ),
    ]
