# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0041_outgoing_as_single_pt2")]

    operations = [
        migrations.RemoveField(model_name="outgoing", name="contacts"),
        migrations.AlterField(
            model_name="outgoing",
            name="contact",
            field=models.ForeignKey(related_name="outgoing_messages", to="contacts.Contact", null=True),
        ),
    ]
