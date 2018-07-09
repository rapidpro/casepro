# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("orgs", "0015_auto_20160209_0926"), ("msgs", "0008_messageaction")]

    operations = [
        migrations.CreateModel(
            name="Label",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("uuid", models.CharField(unique=True, max_length=36)),
                ("name", models.CharField(help_text="Name of this label", max_length=32, verbose_name="Name")),
                ("description", models.CharField(max_length=255, verbose_name="Description")),
                ("keywords", models.CharField(max_length=1024, verbose_name="Keywords", blank=True)),
                ("is_active", models.BooleanField(default=True, help_text="Whether this label is active")),
                ("org", models.ForeignKey(related_name="new_labels", verbose_name="Organization", to="orgs.Org")),
            ],
        ),
        migrations.AddField(
            model_name="messageaction", name="new_label", field=models.ForeignKey(to="msgs.Label", null=True)
        ),
    ]
