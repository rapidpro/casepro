# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0011_auto_20160222_1422")]

    operations = [
        migrations.CreateModel(
            name="Labelling",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="msgs.Label")),
            ],
            options={"db_table": "msgs_message_labels"},
        ),
        migrations.AddField(
            model_name="message",
            name="labels",
            field=models.ManyToManyField(
                help_text="Labels assigned to this message", through="msgs.Labelling", to="msgs.Label"
            ),
        ),
        migrations.AddField(
            model_name="labelling",
            name="message",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="msgs.Message"),
        ),
        migrations.AlterUniqueTogether(name="labelling", unique_together=set([("message", "label")])),
    ]
