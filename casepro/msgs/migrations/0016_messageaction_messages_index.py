# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("msgs", "0015_message_is_active")]

    operations = [
        migrations.RunSQL('CREATE INDEX msgs_messageaction_messages_idx ON msgs_messageaction USING GIN ("messages");')
    ]
