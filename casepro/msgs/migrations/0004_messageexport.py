# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orgs", "0015_auto_20160209_0926"),
        ("msgs", "0003_message_case"),
        ("cases", "0020_delete_messageexport"),
    ]

    operations = [
        migrations.CreateModel(
            name="MessageExport",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("search", models.TextField()),
                ("filename", models.CharField(max_length=512)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(related_name="exports", to=settings.AUTH_USER_MODEL)),
                ("org", models.ForeignKey(related_name="exports", verbose_name="Organization", to="orgs.Org")),
            ],
        )
    ]
