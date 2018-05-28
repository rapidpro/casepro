# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def fix_deleted_users(apps, schema_editor):
    """
    Previously deleting users from orgs caused them to be set as inactive, which then causes difficulties if someone
    tries to re-add that user to an org. This re-activates deleted users and instead removes them from org groups.
    """
    Org = apps.get_model("orgs", "Org")
    User = apps.get_model("auth", "User")

    all_orgs = Org.objects.all()
    inactive_users = list(User.objects.filter(is_active=False))

    for user in inactive_users:
        # remove user from all org groups
        for org in all_orgs:
            org.administrators.remove(user)
            org.editors.remove(user)
            org.viewers.remove(user)

        # remove from any partner for this org
        if user.profile.partner:
            user.profile.partner = None
            user.profile.save(update_fields=("partner",))

        # re-activate user
        user.is_active = True
        user.save(update_fields=("is_active",))

    if inactive_users:
        print("Fixed %d inactive users" % len(inactive_users))


class Migration(migrations.Migration):

    dependencies = [("profiles", "0003_username_max_length")]

    operations = [migrations.RunPython(fix_deleted_users)]
