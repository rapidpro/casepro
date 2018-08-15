# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import django.contrib.postgres.fields
from django.conf import settings
from django.db import migrations, models


def migrate_messageactions(apps, schema_editor):
    MessageActionOld = apps.get_model("cases", "MessageAction")
    MessageAction = apps.get_model("msgs", "MessageAction")

    old_actions = list(MessageActionOld.objects.all())

    for old_action in old_actions:
        MessageAction.objects.create(
            org=old_action.org,
            messages=old_action.messages,
            action=old_action.action,
            created_by=old_action.created_by,
            created_on=old_action.created_on,
            label=old_action.label,
        )

    if old_actions:
        print("Migrated %d message actions to new model in msgs app" % len(old_actions))


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0020_delete_messageexport"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orgs", "0015_auto_20160209_0926"),
        ("msgs", "0007_unhandled_index"),
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
                        max_length=1,
                        choices=[
                            ("F", "Flag"),
                            ("N", "Un-flag"),
                            ("L", "Label"),
                            ("U", "Remove Label"),
                            ("A", "Archive"),
                            ("R", "Restore"),
                        ],
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
        migrations.RunPython(migrate_messageactions),
    ]
