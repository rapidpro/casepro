# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0008_org_timezone'),
    ]

    operations = [
        migrations.CreateModel(
            name='Label',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(unique=True, max_length=36)),
                ('name', models.CharField(help_text='Name of this label', max_length=32, verbose_name='Name')),
                ('org', models.ForeignKey(related_name='labels', verbose_name='Organization', to='orgs.Org')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
