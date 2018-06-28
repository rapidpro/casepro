# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0007_contact_is_stub")]

    operations = [
        # index for faster lookups during sync
        migrations.RunSQL("CREATE INDEX contacts_contact_org_uuid ON contacts_contact(org_id, uuid)")
    ]
