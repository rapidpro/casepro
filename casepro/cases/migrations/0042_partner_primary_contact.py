# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0041_partner_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='primary_contact',
            field=models.ForeignKey(related_name='partners', verbose_name='Primary Contact', blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]
