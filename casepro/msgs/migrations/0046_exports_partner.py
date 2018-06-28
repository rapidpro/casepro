# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0036_caseexport_partner"), ("msgs", "0045_replyexport")]

    operations = [
        migrations.AddField(
            model_name="messageexport",
            name="partner",
            field=models.ForeignKey(related_name="messageexports", to="cases.Partner", null=True),
        ),
        migrations.AddField(
            model_name="replyexport",
            name="partner",
            field=models.ForeignKey(related_name="replyexports", to="cases.Partner", null=True),
        ),
    ]
