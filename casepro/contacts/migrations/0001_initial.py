# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields.hstore
from django.contrib.postgres.operations import HStoreExtension


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0014_auto_20150722_1419'),
    ]

    operations = [
        HStoreExtension(),
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(unique=True, max_length=36)),
                ('name', models.CharField(help_text='The name of this contact', max_length=128, verbose_name='Full name', blank=True)),
                ('fields', django.contrib.postgres.fields.hstore.HStoreField(help_text='Custom contact field values', verbose_name='Fields')),
                ('language', models.CharField(help_text='Language for this contact', max_length=3, null=True, verbose_name='Language', blank=True)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this contact is active')),
                ('created_on', models.DateTimeField(help_text='When this contact was created', auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(unique=True, max_length=36)),
                ('name', models.CharField(max_length=64)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this group is active')),
                ('created_on', models.DateTimeField(help_text='When this group was created', auto_now_add=True)),
                ('org', models.ForeignKey(related_name='new_groups', verbose_name='Organization', to='orgs.Org')),
            ],
        ),
        migrations.AddField(
            model_name='contact',
            name='groups',
            field=models.ManyToManyField(related_name='contacts', to='contacts.Group'),
        ),
        migrations.AddField(
            model_name='contact',
            name='org',
            field=models.ForeignKey(related_name='new_contacts', verbose_name='Organization', to='orgs.Org'),
        ),
    ]
