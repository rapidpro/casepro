# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0016_taskstate_is_disabled'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0037_partner_is_restricted'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyOrgCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=1)),
                ('day', models.DateField(help_text='The day this count is for')),
                ('count', models.PositiveIntegerField(default=1)),
                ('squashed', models.BooleanField(default=False)),
                ('org', models.ForeignKey(to='orgs.Org')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='DailyOrgUserCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=1)),
                ('day', models.DateField(help_text='The day this count is for')),
                ('count', models.PositiveIntegerField(default=1)),
                ('squashed', models.BooleanField(default=False)),
                ('org', models.ForeignKey(to='orgs.Org')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='DailyPartnerCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=1)),
                ('day', models.DateField(help_text='The day this count is for')),
                ('count', models.PositiveIntegerField(default=1)),
                ('squashed', models.BooleanField(default=False)),
                ('partner', models.ForeignKey(to='cases.Partner')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
