# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orgs", "0008_org_timezone"),
        ("cases", "0006_auto_20150508_0912"),
    ]

    operations = [
        migrations.CreateModel(
            name="Outgoing",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("broadcast_id", models.IntegerField()),
                ("created_on", models.DateTimeField(db_index=True)),
                (
                    "case",
                    models.ForeignKey(related_name="outgoing", to="cases.Case", null=True, on_delete=models.PROTECT),
                ),
                (
                    "created_by",
                    models.ForeignKey(related_name="outgoing", to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT),
                ),
                (
                    "org",
                    models.ForeignKey(
                        related_name="outgoing", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
                    ),
                ),
            ],
        )
    ]
