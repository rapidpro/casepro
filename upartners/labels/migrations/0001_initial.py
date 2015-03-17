# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0008_org_timezone'),
        ('partners', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Label',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text='Name of this label', max_length=32, verbose_name='Name')),
                ('description', models.CharField(max_length=255, verbose_name='Description')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this label is active')),
                ('org', models.ForeignKey(related_name='labels', verbose_name='Organization', to='orgs.Org')),
                ('partners', models.ManyToManyField(help_text='Partner organizations who can access messages with this label', related_name='labels', to='partners.Partner')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
