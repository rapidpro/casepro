# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def populate_case_contacts(apps, schema_editor):
    Case = apps.get_model("cases", "Case")
    Contact = apps.get_model("cases", "Contact")

    for case in Case.objects.all():
        contact = Contact.objects.filter(uuid=case.contact_uuid).first()
        if not contact:
            contact = Contact.objects.create(org=case.org, uuid=case.contact_uuid, suspended_groups=[])

        case.contact = contact
        case.save(update_fields=("contact",))


class Migration(migrations.Migration):

    dependencies = [("cases", "0015_contact")]

    operations = [
        migrations.AddField(
            model_name="case",
            name="contact",
            field=models.ForeignKey(related_name="cases", to="cases.Contact", null=True, on_delete=models.PROTECT),
        ),
        migrations.RunPython(populate_case_contacts),
        migrations.AlterField(
            model_name="case",
            name="contact",
            field=models.ForeignKey(related_name="cases", to="cases.Contact", on_delete=models.PROTECT),
        ),
        migrations.RemoveField(model_name="case", name="contact_uuid"),
    ]
