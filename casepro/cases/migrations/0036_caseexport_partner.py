# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0035_folder_indexes")]

    operations = [
        migrations.AddField(
            model_name="caseexport",
            name="partner",
            field=models.ForeignKey(related_name="caseexports", to="cases.Partner", null=True),
        )
    ]
