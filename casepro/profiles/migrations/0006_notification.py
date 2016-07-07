# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0039_populate_case_watchers'),
        ('msgs', '0050_label_watchers'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('profiles', '0005_fix_admins_with_partners'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=1)),
                ('is_sent', models.BooleanField(default=False)),
                ('created_on', models.DateTimeField(default=django.utils.timezone.now)),
                ('case_action', models.ForeignKey(to='cases.CaseAction', null=True)),
                ('message', models.ForeignKey(to='msgs.Message', null=True)),
                ('user', models.ForeignKey(related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
