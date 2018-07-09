# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import json

from django.db import migrations


def create_suspend_groups(apps, schema_editor):
    Org = apps.get_model("orgs", "Org")
    Group = apps.get_model("contacts", "Group")

    num_created = 0
    num_updated = 0

    for org in Org.objects.all():
        config = json.loads(org.config) if org.config else {}
        suspend_groups = config.get("suspend_groups", [])

        for group_uuid in suspend_groups:
            group = Group.objects.filter(org=org, uuid=group_uuid).first()
            if group:
                group.suspend_from = True
                group.save(update_fields=("suspend_from",))
                num_updated += 1
            else:
                # create placeholder which will be updated in next contacts sync
                Group.objects.create(org=org, uuid=group_uuid, name="Syncing...", suspend_from=True, is_active=False)
                num_created += 1

    if num_created or num_updated:
        print("Migrated org suspend groups (%d created, %d updated)" % (num_created, num_updated))


class Migration(migrations.Migration):

    dependencies = [("contacts", "0010_group_suspend_from")]

    operations = [migrations.RunPython(create_suspend_groups)]
