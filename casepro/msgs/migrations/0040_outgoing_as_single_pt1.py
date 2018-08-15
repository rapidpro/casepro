# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0039_outgoing_text_non_null")]

    operations = [
        migrations.AlterField(
            model_name="outgoing",
            name="backend_id",
            field=models.IntegerField(help_text="Broadcast id from the backend", null=True),
        ),
        migrations.RenameField(model_name="outgoing", old_name="backend_id", new_name="backend_broadcast_id"),
        migrations.RemoveField(model_name="outgoing", name="recipient_count"),
        migrations.AddField(
            model_name="outgoing",
            name="contact",
            field=models.ForeignKey(to="contacts.Contact", null=True, on_delete=models.PROTECT),
        ),
    ]
