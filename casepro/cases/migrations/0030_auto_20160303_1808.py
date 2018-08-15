# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0029_auto_20160303_1215")]

    operations = [
        migrations.RemoveField(model_name="case", name="message_id"),
        migrations.AlterField(
            model_name="case",
            name="contact",
            field=models.ForeignKey(related_name="cases", to="contacts.Contact", on_delete=models.PROTECT),
        ),
        migrations.AlterField(
            model_name="case",
            name="initial_message",
            field=models.OneToOneField(related_name="initial_case", to="msgs.Message", on_delete=models.PROTECT),
        ),
    ]
