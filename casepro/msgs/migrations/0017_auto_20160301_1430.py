# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0016_messageaction_messages_index")]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="labels",
            field=models.ManyToManyField(
                help_text="Labels assigned to this message",
                through="msgs.Labelling",
                related_name="messages",
                to="msgs.Label",
            ),
        )
    ]
