# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0039_populate_case_watchers'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='user_assignee',
            field=models.ForeignKey(related_name='cases', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, help_text='The (optional) user that this case is assigned to', null=True),
        ),
    ]
