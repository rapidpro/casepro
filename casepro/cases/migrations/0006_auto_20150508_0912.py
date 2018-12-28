# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0005_auto_20150424_1427")]

    operations = [
        migrations.CreateModel(
            name="CaseEvent",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("event", models.CharField(max_length=1, choices=[("R", "Contact replied")])),
                ("created_on", models.DateTimeField(db_index=True)),
            ],
        ),
        migrations.AlterField(
            model_name="case",
            name="opened_on",
            field=models.DateTimeField(help_text="When this case was opened", auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="caseaction", name="created_on", field=models.DateTimeField(auto_now_add=True, db_index=True)
        ),
        migrations.AlterField(
            model_name="messageaction",
            name="action",
            field=models.CharField(
                max_length=1,
                choices=[
                    ("F", "Flag"),
                    ("N", "Un-flag"),
                    ("L", "Label"),
                    ("U", "Remove Label"),
                    ("A", "Archive"),
                    ("R", "Restore"),
                ],
            ),
        ),
        migrations.AddField(
            model_name="caseevent",
            name="case",
            field=models.ForeignKey(related_name="events", to="cases.Case", on_delete=models.PROTECT),
        ),
    ]
