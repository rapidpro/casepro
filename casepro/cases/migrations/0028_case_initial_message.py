# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def populate_initial_message(apps, schema_editor):
    Message = apps.get_model("msgs", "Message")
    Case = apps.get_model("cases", "Case")

    cases = list(Case.objects.all())
    num_missing = 0

    for case in cases:
        message = Message.objects.filter(org=case.org, backend_id=case.message_id).select_related("contact").first()
        if message:
            case.contact = message.contact
            case.initial_message = message
            case.save(update_fields=("initial_message",))
        else:
            print("Missing message #%d for org #%d" % (case.message_id, case.org_id))
            num_missing += 1

    if cases:
        print("Updated %d cases (%d missing messages)" % (len(cases), num_missing))


class Migration(migrations.Migration):

    dependencies = [("msgs", "0020_auto_20160303_1058"), ("cases", "0027_auto_20160222_1250")]

    operations = [
        migrations.AddField(
            model_name="case",
            name="initial_message",
            field=models.OneToOneField(
                related_name="initial_case", null=True, to="msgs.Message", on_delete=models.PROTECT
            ),
        ),
        migrations.RunPython(populate_initial_message),
        migrations.RemoveField(model_name="case", name="message_on"),
    ]
