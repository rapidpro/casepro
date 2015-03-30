# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0008_org_timezone'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('partners', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Case',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('contact_uuid', models.CharField(max_length=36)),
                ('opened_on', models.DateTimeField(help_text='When this case was opened', auto_now_add=True)),
                ('closed_on', models.DateTimeField(help_text='When this case was closed', null=True)),
                ('org', models.ForeignKey(related_name='cases', verbose_name='Organization', to='orgs.Org')),
                ('partner', models.ForeignKey(related_name='cases', to='partners.Partner')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CaseAction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action', models.CharField(max_length=1, choices=[('O', 'Open'), ('N', 'Add Note'), ('A', 'Reassign'), ('C', 'Close'), ('R', 'Reopen')])),
                ('performed_on', models.DateTimeField(auto_now_add=True)),
                ('note', models.CharField(max_length=1024, null=True)),
                ('assignee', models.ForeignKey(related_name='case_actions', to='partners.Partner', null=True)),
                ('case', models.ForeignKey(related_name='history', to='cases.Case')),
                ('performed_by', models.ForeignKey(related_name='case_actions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('pk',),
            },
            bases=(models.Model,),
        ),
    ]
