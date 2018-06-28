# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("cases", "0042_auto_20160805_1003")]

    operations = [
        migrations.AddField(
            model_name="case",
            name="user_assignee",
            field=models.ForeignKey(
                related_name="cases",
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                help_text="The (optional) user that this case is assigned to",
                null=True,
            ),
        )
    ]
