# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0012_message_labels")]

    operations = [
        migrations.AlterField(
            model_name="label",
            name="org",
            field=models.ForeignKey(related_name="labels", verbose_name="Organization", to="orgs.Org"),
        )
    ]
