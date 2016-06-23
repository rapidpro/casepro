# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0016_taskstate_is_disabled'),
        ('msgs', '0047_outgoing_urn'),
    ]

    operations = [
        migrations.CreateModel(
            name='Language',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=6)),
                ('name', models.CharField(max_length=100, null=True, blank=True)),
                ('location', models.CharField(max_length=100, null=True, blank=True)),
                ('org', models.ForeignKey(related_name='languages', verbose_name='Organization', to='orgs.Org')),
            ],
        ),
    ]
