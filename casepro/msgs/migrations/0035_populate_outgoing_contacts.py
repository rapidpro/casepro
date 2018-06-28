# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def populate_outgoing_contacts(apps, schema_editor):
    Outgoing = apps.get_model("msgs", "Outgoing")
    for outgoing in Outgoing.objects.exclude(case=None).select_related("case__contact"):
        outgoing.contacts.add(outgoing.case.contact)


class Migration(migrations.Migration):

    dependencies = [("msgs", "0034_auto_20160512_1200")]

    operations = [migrations.RunPython(populate_outgoing_contacts)]
