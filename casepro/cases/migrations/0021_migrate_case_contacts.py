# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def migrate_case_contacts(apps, schema_editor):
    Case = apps.get_model("cases", "Case")
    Contact = apps.get_model("contacts", "Contact")
    Group = apps.get_model("contacts", "Group")

    num_contacts_created = 0
    num_groups_created = 0

    cases = list(Case.objects.all().select_related("org", "contact_old"))

    for case in cases:
        org = case.org
        contact_uuid = case.contact_old.uuid

        contact = Contact.objects.filter(org=org, uuid=contact_uuid).first()
        if not contact:
            contact = Contact.objects.create(org=org, uuid=contact_uuid, is_stub=True)
            num_contacts_created += 1

        case.contact = contact
        case.save(update_fields=("contact",))

        for group_uuid in case.contact_old.suspended_groups:
            group = Group.objects.filter(org=org, uuid=group_uuid).first()
            if not group:
                group = Group.objects.create(org=org, uuid=group_uuid, name="Syncing...", is_active=False)
                num_groups_created += 1

            contact.suspended_groups.add(group)

    if cases:
        print(
            "Migrated %d case contacts (%d created, %d groups created)"
            % (len(cases), num_contacts_created, num_groups_created)
        )


class Migration(migrations.Migration):

    dependencies = [("cases", "0020_delete_messageexport"), ("contacts", "0013_migrate_org_fields")]

    operations = [
        migrations.RenameField(model_name="case", old_name="contact", new_name="contact_old"),
        migrations.AlterField(
            model_name="case",
            name="contact_old",
            field=models.ForeignKey(related_name="cases_old", to="cases.Contact"),
        ),
        migrations.AddField(
            model_name="case",
            name="contact",
            field=models.ForeignKey(related_name="cases", to="contacts.Contact", null=True),
        ),
        migrations.RunPython(migrate_case_contacts),
        migrations.RemoveField(model_name="case", name="contact_old"),
        migrations.RemoveField(model_name="contact", name="org"),
        migrations.DeleteModel(name="Contact"),
    ]
