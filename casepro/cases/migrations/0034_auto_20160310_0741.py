# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0033_caseexport")]

    operations = [
        migrations.AlterField(
            model_name="case",
            name="opened_on",
            field=models.DateTimeField(help_text="When this case was opened", auto_now_add=True),
        )
    ]
