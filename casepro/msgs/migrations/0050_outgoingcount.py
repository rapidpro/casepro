# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0016_taskstate_is_disabled'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0037_partner_is_restricted'),
        ('msgs', '0049_remove_label_tests'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutgoingCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=1)),
                ('day', models.DateField(help_text='The day this count is for')),
                ('count', models.PositiveIntegerField()),
                ('org', models.ForeignKey(to='orgs.Org')),
                ('partner', models.ForeignKey(to='cases.Partner', null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
    ]
