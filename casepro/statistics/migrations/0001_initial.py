# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DailyCount",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("day", models.DateField(help_text="The day this count is for")),
                ("item_type", models.CharField(help_text="The thing being counted", max_length=1)),
                ("scope", models.CharField(help_text="The scope in which it is being counted", max_length=32)),
                ("count", models.PositiveIntegerField()),
            ],
        ),
        migrations.AlterIndexTogether(name="dailycount", index_together=set([("item_type", "scope", "day")])),
    ]
