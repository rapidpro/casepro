# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def fix_admins_with_partners(apps, schema_editor):
    Org = apps.get_model("orgs", "Org")

    for org in Org.objects.all():
        for admin in org.administrators.all():
            # admins should't also be in other permission groups
            org.editors.remove(admin)
            org.viewers.remove(admin)

            # and shouldn't have a partner for this org
            if admin.profile.partner and admin.profile.partner.org == org:
                partner = admin.profile.partner

                admin.profile.partner = None
                admin.profile.save(update_fields=("partner",))

                print("Removed admin %s from partner %s" % (admin.email, partner.name))


class Migration(migrations.Migration):

    dependencies = [("profiles", "0004_fix_deleted_users")]

    operations = [migrations.RunPython(fix_admins_with_partners)]
