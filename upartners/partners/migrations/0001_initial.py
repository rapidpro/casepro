# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0008_org_timezone'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('labels', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Partner',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text='Name of this partner organization', max_length=128, verbose_name='Name')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this group is active')),
                ('analysts', models.ManyToManyField(help_text='Users who can view this partner organization', related_name='analyst_partners', verbose_name='Data Analysts', to=settings.AUTH_USER_MODEL)),
                ('labels', models.ManyToManyField(help_text='Message labels visible to this partner', related_name='partners', to='labels.Label')),
                ('managers', models.ManyToManyField(help_text='Users who can manage this partner organization', related_name='manage_partners', verbose_name='Managers', to=settings.AUTH_USER_MODEL)),
                ('org', models.ForeignKey(related_name='partners', verbose_name='Organization', to='orgs.Org')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
