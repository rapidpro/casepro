# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from dash.utils import chunks
from django.db import migrations


def split_outgoings(apps, schema_editor):
    Outgoing = apps.get_model("msgs", "Outgoing")

    outgoing_ids = Outgoing.objects.all().values_list("pk", flat=True)

    for id_batch in chunks(outgoing_ids, 1000):
        outgoings = (
            Outgoing.objects.filter(pk__in=id_batch).select_related("org", "partner").prefetch_related("contacts")
        )

        for outgoing in outgoings:
            contacts = list(outgoing.contacts.all())

            if len(contacts) > 0:
                outgoing.contact = contacts[0]
                outgoing.save(update_fields=("contact",))

                if len(contacts) > 1:
                    for other_contact in contacts[1:]:
                        Outgoing.objects.create(
                            org=outgoing.org,
                            partner=outgoing.partner,
                            text=outgoing.text,
                            backend_broadcast_id=outgoing.backend_broadcast_id,
                            contact=other_contact,
                            urns=outgoing.urns,
                            created_by=outgoing.created_by,
                            created_on=outgoing.created_on,
                            case=outgoing.case,
                        )

                    print(
                        "Split outgoing message #%d into %d single-recipient messages" % (outgoing.pk, len(contacts))
                    )


class Migration(migrations.Migration):

    dependencies = [("msgs", "0040_outgoing_as_single_pt1")]

    operations = [migrations.RunPython(split_outgoings)]
