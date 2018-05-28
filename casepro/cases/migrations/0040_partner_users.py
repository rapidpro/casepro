# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cases", "0039_populate_case_watchers"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="users",
            field=models.ManyToManyField(
                help_text="Users that belong to this partner", related_name="partners", to=settings.AUTH_USER_MODEL
            ),
        )
    ]
