# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations


def unset_dynamic_suspend_groups(apps, schema_editor):
    Group = apps.get_model("contacts", "Group")
    num_updated = Group.objects.filter(is_dynamic=True, suspend_from=True).update(suspend_from=False)
    if num_updated:
        print("Updated %d dynamic groups to not be suspend_from groups")


class Migration(migrations.Migration):

    dependencies = [("contacts", "0019_group_is_dynamic")]

    operations = [migrations.RunPython(unset_dynamic_suspend_groups)]
