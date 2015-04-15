# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0008_org_timezone'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageExport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('search', models.TextField()),
                ('filename', models.CharField(max_length=512)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(related_name='exports', to=settings.AUTH_USER_MODEL)),
                ('org', models.ForeignKey(related_name='exports', verbose_name='Organization', to='orgs.Org')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
