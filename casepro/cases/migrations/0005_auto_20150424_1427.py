# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orgs", "0008_org_timezone"),
        ("cases", "0004_auto_20150421_1242"),
    ]

    operations = [
        migrations.CreateModel(
            name="MessageAction",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("messages", django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=None)),
                (
                    "action",
                    models.CharField(
                        max_length=1, choices=[("F", "Flag"), ("N", "Un-flag"), ("L", "Label"), ("A", "Archive")]
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        related_name="message_actions", to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT
                    ),
                ),
                ("label", models.ForeignKey(to="cases.Label", null=True, on_delete=models.PROTECT)),
                (
                    "org",
                    models.ForeignKey(
                        related_name="message_actions",
                        verbose_name="Organization",
                        to="orgs.Org",
                        on_delete=models.PROTECT,
                    ),
                ),
            ],
        ),
        migrations.RunSQL(
            'CREATE INDEX cases_messageaction_messages_idx ON cases_messageaction USING GIN ("messages");'
        ),
        migrations.AlterModelOptions(name="caseaction", options={}),
    ]
