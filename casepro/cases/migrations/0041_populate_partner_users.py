# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def populate_partner_users(apps, schema_editor):
    User = apps.get_model("auth", "User")

    for user in User.objects.exclude(profile__partner=None):
        partner = user.profile.partner
        org = partner.org

        if user in org.editors.all() or user in org.viewers.all():
            partner.users.add(user)
        else:
            print("User %s no longer has permissions in org %s to be a partner user" % (user.email, org.name))


class Migration(migrations.Migration):

    dependencies = [("cases", "0040_partner_users")]

    operations = [migrations.RunPython(populate_partner_users)]
