# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0022_folder_indexes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messageexport',
            name='created_by',
            field=models.ForeignKey(related_name='messageexports', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='messageexport',
            name='org',
            field=models.ForeignKey(related_name='messageexports', verbose_name='Organization', to='orgs.Org'),
        ),
    ]
