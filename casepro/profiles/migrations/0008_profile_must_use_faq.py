# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("profiles", "0007_remove_profile_partner")]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="must_use_faq",
            field=models.BooleanField(
                default=False, help_text="User is only allowed to reply with pre-approved responses"
            ),
        )
    ]
