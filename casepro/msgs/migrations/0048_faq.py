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
            name='FAQ',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('question', models.CharField(max_length=140)),
                ('answer', models.CharField(max_length=140)),
                ('labels', models.ManyToManyField(help_text='Labels assigned to this FAQ', related_name='faqs', to='msgs.Label')),
                ('language', models.ForeignKey(related_name='faqs', default=None, verbose_name='Language', to='msgs.Language')),
                ('org', models.ForeignKey(related_name='faqs', verbose_name='Organization', to='orgs.Org')),
                ('parent', models.ForeignKey(related_name='translations', blank=True, to='msgs.FAQ', null=True)),
            ],
        ),
    ]
