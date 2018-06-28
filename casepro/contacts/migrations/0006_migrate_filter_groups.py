# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def migrate_filter_groups(apps, schema_editor):
    OldGroup = apps.get_model("cases", "Group")
    Group = apps.get_model("contacts", "Group")

    old_groups = list(OldGroup.objects.filter(is_active=True))

    num_created = 0
    num_updated = 0

    # old filter groups are now just a visibility flag on the new group model
    for old in old_groups:
        new = Group.objects.filter(uuid=old.uuid).first()
        if new:
            new.is_visible = True
            new.save(update_fields=("is_visible",))
            num_updated += 1
        else:
            # create placeholder which will be updated in next contacts sync
            Group.objects.create(org=old.org, uuid=old.uuid, name="Syncing...", is_visible=True, is_active=False)
            num_created += 1

    if old_groups:
        print(
            "Migrated %d old filter groups (%d new groups created, %d updated)"
            % (len(old_groups), num_created, num_updated)
        )


class Migration(migrations.Migration):

    dependencies = [("contacts", "0005_group_is_visible"), ("cases", "0001_initial")]

    operations = [migrations.RunPython(migrate_filter_groups)]
