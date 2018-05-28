# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import json

from django.db import migrations, models


def migrate_contact_fields(apps, schema_editor):
    Org = apps.get_model("orgs", "Org")
    Field = apps.get_model("contacts", "Field")

    num_created = 0
    num_updated = 0

    for org in Org.objects.all():
        config = json.loads(org.config) if org.config else {}
        contact_fields = config.get("contact_fields", [])

        for field_key in contact_fields:
            field = Field.objects.filter(org=org, key=field_key).first()
            if field:
                field.is_visible = True
                field.save(update_fields=("is_visible",))
                num_updated += 1
            else:
                # create placeholder which will be updated in next contacts sync
                Field.objects.create(org=org, key=field_key, label="Syncing...", is_visible=True, is_active=False)
                num_created += 1

    if num_created or num_updated:
        print("Migrated org contact fields (%d created, %d updated)" % (num_created, num_updated))


class Migration(migrations.Migration):

    dependencies = [("contacts", "0012_field_is_visible")]

    operations = [migrations.RunPython(migrate_contact_fields)]
