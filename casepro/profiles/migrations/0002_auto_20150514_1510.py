# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("profiles", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="partner",
            field=models.ForeignKey(
                related_name="user_profiles", to="cases.Partner", null=True, on_delete=models.PROTECT
            ),
        )
    ]
