# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0036_caseexport_partner")]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="is_restricted",
            field=models.BooleanField(
                default=True,
                help_text="Whether this partner's access is restricted by labels",
                verbose_name="Restricted Access",
            ),
        )
    ]
