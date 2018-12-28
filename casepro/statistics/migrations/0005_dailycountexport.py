# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orgs", "0016_taskstate_is_disabled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("statistics", "0004_populate_incomining_counts"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyCountExport",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("filename", models.CharField(max_length=512)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("type", models.CharField(max_length=1)),
                ("since", models.DateField()),
                ("until", models.DateField()),
                (
                    "created_by",
                    models.ForeignKey(
                        related_name="dailycountexports", to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT
                    ),
                ),
                (
                    "org",
                    models.ForeignKey(
                        related_name="dailycountexports",
                        verbose_name="Organization",
                        to="orgs.Org",
                        on_delete=models.PROTECT,
                    ),
                ),
            ],
            options={"abstract": False},
        )
    ]
