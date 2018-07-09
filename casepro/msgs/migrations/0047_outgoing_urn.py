# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def populate_outgoing_urn(apps, schema_editor):
    Outgoing = apps.get_model("msgs", "Outgoing")

    fwds = Outgoing.objects.filter(activity="F")

    for fwd in fwds:
        fwd.urn = fwd.urns[0] if fwd.urns else ""
        fwd.save(update_fields=("urn",))

    if fwds:
        print("Updated %d forwards" % len(fwds))


class Migration(migrations.Migration):

    dependencies = [("msgs", "0046_exports_partner")]

    operations = [
        migrations.AddField(model_name="outgoing", name="urn", field=models.CharField(max_length=255, null=True)),
        migrations.RunPython(populate_outgoing_urn),
        migrations.RemoveField(model_name="outgoing", name="urns"),
    ]
