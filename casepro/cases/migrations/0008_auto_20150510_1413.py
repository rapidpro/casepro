# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0007_outgoing")]

    operations = [
        migrations.AddField(
            model_name="outgoing",
            name="activity",
            field=models.CharField(
                default="B", max_length=1, choices=[("B", "Bulk Reply"), ("C", "Case Reply"), ("F", "Forward")]
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="outgoing",
            name="recipient_count",
            field=models.PositiveIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="outgoing",
            name="case",
            field=models.ForeignKey(
                related_name="outgoing_messages", to="cases.Case", null=True, on_delete=models.PROTECT
            ),
        ),
        migrations.AlterField(
            model_name="outgoing",
            name="created_by",
            field=models.ForeignKey(
                related_name="outgoing_messages", to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT
            ),
        ),
        migrations.AlterField(
            model_name="outgoing",
            name="org",
            field=models.ForeignKey(
                related_name="outgoing_messages", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
            ),
        ),
    ]
