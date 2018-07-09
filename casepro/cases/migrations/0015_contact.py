# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0014_label_uuid_not_null")]

    operations = [
        migrations.CreateModel(
            name="Contact",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("uuid", models.CharField(unique=True, max_length=36)),
                (
                    "suspended_groups",
                    django.contrib.postgres.fields.ArrayField(
                        help_text="UUIDs of suspended contact groups",
                        base_field=models.CharField(max_length=36),
                        size=None,
                    ),
                ),
                ("org", models.ForeignKey(related_name="contacts", verbose_name="Organization", to="orgs.Org")),
            ],
        )
    ]
