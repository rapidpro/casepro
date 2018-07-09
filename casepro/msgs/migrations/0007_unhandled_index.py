# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0006_message_is_handled")]

    operations = [
        # index for faster lookups during sync
        migrations.RunSQL("CREATE INDEX msgs_message_org_unhandled ON msgs_message(org_id) WHERE is_handled = FALSE;")
    ]
