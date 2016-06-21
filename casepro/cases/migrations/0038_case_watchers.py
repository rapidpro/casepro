# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0037_partner_is_restricted'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='watchers',
            field=models.ManyToManyField(help_text='Users to notified of case activity', to=settings.AUTH_USER_MODEL),
        ),
    ]
