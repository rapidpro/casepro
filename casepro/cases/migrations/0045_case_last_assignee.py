# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0044_auto_20160812_1612'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='last_assignee',
            field=models.ForeignKey(related_name='previously_assigned_cases', to='cases.Partner', null=True),
        ),
        migrations.AddField(
            model_name='case',
            name='last_reassigned_on',
            field=models.DateTimeField(help_text='When this case was last reassigned', null=True),
        ),
        migrations.AddField(
            model_name='case',
            name='last_user_assignee',
            field=models.ForeignKey(related_name='previously_assigned_cases', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]
