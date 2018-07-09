# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0018_delete_outgoing"), ("msgs", "0002_outgoing")]

    operations = [
        migrations.AddField(
            model_name="message",
            name="case",
            field=models.ForeignKey(related_name="incoming_messages", to="cases.Case", null=True),
        ),
        migrations.AlterField(
            model_name="message",
            name="org",
            field=models.ForeignKey(related_name="incoming_messages", verbose_name="Organization", to="orgs.Org"),
        ),
    ]
