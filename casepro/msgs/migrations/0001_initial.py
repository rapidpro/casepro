# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0003_auto_20160209_1048"), ("orgs", "0014_auto_20150722_1419")]

    operations = [
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("type", models.CharField(max_length=1)),
                ("text", models.TextField(max_length=640, verbose_name="Text")),
                ("is_archived", models.BooleanField(default=False)),
                ("created_on", models.DateTimeField()),
                ("contact", models.ForeignKey(to="contacts.Contact", on_delete=models.PROTECT)),
                (
                    "org",
                    models.ForeignKey(
                        related_name="messages", verbose_name="Org", to="orgs.Org", on_delete=models.PROTECT
                    ),
                ),
            ],
        )
    ]
