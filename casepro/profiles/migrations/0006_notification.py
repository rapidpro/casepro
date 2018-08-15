# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

INDEX_SQL = """
-- for displaying a user's latest notifications in a given org
CREATE INDEX profiles_notification_org_user_created_on ON profiles_notification(org_id, user_id, created_on DESC);

-- for fetching unsent notifications that need to be sent in order
CREATE INDEX profiles_notification_created_on_unsent ON profiles_notification(created_on ASC) WHERE is_sent = FALSE;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0039_populate_case_watchers"),
        ("msgs", "0050_label_watchers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orgs", "0016_taskstate_is_disabled"),
        ("profiles", "0005_fix_admins_with_partners"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("type", models.CharField(max_length=1)),
                ("is_sent", models.BooleanField(default=False)),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                ("case_action", models.ForeignKey(to="cases.CaseAction", null=True, on_delete=models.PROTECT)),
                ("message", models.ForeignKey(to="msgs.Message", null=True, on_delete=models.PROTECT)),
                ("org", models.ForeignKey(to="orgs.Org", on_delete=models.PROTECT)),
                (
                    "user",
                    models.ForeignKey(
                        related_name="notifications", to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT
                    ),
                ),
            ],
        ),
        migrations.RunSQL(INDEX_SQL),
    ]
