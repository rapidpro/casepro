# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations


def populate_message_case(apps, schema_editor):
    Case = apps.get_model("cases", "Case")
    Message = apps.get_model("msgs", "Message")

    cases = list(Case.objects.select_related("initial_message").order_by("org", "opened_on"))
    num_updated = 0

    for case in cases:
        missing_messages = Message.objects.filter(org=case.org, contact=case.contact, case=None)
        missing_messages = missing_messages.filter(created_on__gte=case.opened_on)

        if case.closed_on:
            missing_messages = missing_messages.filter(created_on__lte=case.closed_on)

        num_updated += missing_messages.update(case=case)

        if case.initial_message.case != case:
            case.initial_message.case = case
            case.initial_message.save(update_fields=("case",))
            num_updated += 1

    if cases:
        print("Attached %d missing messages to %d cases" % (num_updated, len(cases)))


class Migration(migrations.Migration):

    dependencies = [("cases", "0031_remove_caseevent")]

    operations = [migrations.RunPython(populate_message_case)]
