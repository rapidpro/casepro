# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.conf import settings
from django.db import migrations, models


def data_migration(apps, schema_editor):
    OldOutgoing = apps.get_model("cases", "Outgoing")
    NewOutgoing = apps.get_model("msgs", "Outgoing")

    outgoings = list(OldOutgoing.objects.all().select_related("created_by", "case"))

    for old in outgoings:
        NewOutgoing.objects.create(
            org=old.org,
            activity=old.activity,
            text=old.text,
            broadcast_id=old.broadcast_id,
            recipient_count=old.recipient_count,
            created_by=old.created_by,
            created_on=old.created_on,
            case=old.case,
        )

    if outgoings:
        print("Migrated %d outgoing messages to new model in msgs app" % len(outgoings))


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0017_outgoing_text"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orgs", "0014_auto_20150722_1419"),
        ("msgs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Outgoing",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "activity",
                    models.CharField(
                        max_length=1, choices=[("B", "Bulk Reply"), ("C", "Case Reply"), ("F", "Forward")]
                    ),
                ),
                ("text", models.TextField(max_length=640, null=True)),
                ("broadcast_id", models.IntegerField()),
                ("recipient_count", models.PositiveIntegerField()),
                ("created_on", models.DateTimeField(db_index=True)),
                ("case", models.ForeignKey(related_name="outgoing_messages", to="cases.Case", null=True)),
                ("created_by", models.ForeignKey(related_name="outgoing_messages", to=settings.AUTH_USER_MODEL)),
                (
                    "org",
                    models.ForeignKey(related_name="outgoing_messages", verbose_name="Organization", to="orgs.Org"),
                ),
            ],
        ),
        migrations.RunPython(data_migration),
    ]
