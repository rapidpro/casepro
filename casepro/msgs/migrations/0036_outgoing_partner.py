# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def populate_outgoing_partner(apps, schema_editor):
    Partner = apps.get_model("cases", "Partner")
    Outgoing = apps.get_model("msgs", "Outgoing")

    num_updated = 0

    for partner in Partner.objects.all().prefetch_related("user_profiles"):
        partner_profiles = partner.user_profiles.all()
        partner_users = [p.user for p in partner_profiles.all()]

        num_updated += Outgoing.objects.filter(org=partner.org, created_by__in=partner_users).update(partner=partner)

    if num_updated:
        print("Updated %d outgoing messages with partner orgs" % num_updated)


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0035_folder_indexes"),
        ("msgs", "0035_populate_outgoing_contacts"),
        ("profiles", "0003_username_max_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="outgoing",
            name="partner",
            field=models.ForeignKey(related_name="outgoing_messages", to="cases.Partner", null=True),
        ),
        migrations.RunPython(populate_outgoing_partner),
    ]
