# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def migrate_labels(apps, schema_editor):
    Org = apps.get_model("orgs", "Org")
    OldLabel = apps.get_model("cases", "Label")
    NewLabel = apps.get_model("msgs", "Label")
    CaseAction = apps.get_model("cases", "CaseAction")
    MessageAction = apps.get_model("msgs", "MessageAction")

    for org in Org.objects.all():
        print("Migrating labels for org %s #%d..." % (org.name, org.pk))

        for old_label in OldLabel.objects.filter(org=org):
            new_label = NewLabel.objects.create(
                org=org,
                uuid=old_label.uuid,
                name=old_label.name,
                description=old_label.description,
                keywords=old_label.keywords,
                is_active=old_label.is_active,
            )
            for partner in old_label.partners.all():
                partner.new_labels.add(new_label)

            for case in old_label.cases.all():
                case.new_labels.add(new_label)

            CaseAction.objects.filter(label=old_label).update(new_label=new_label)
            MessageAction.objects.filter(label=old_label).update(new_label=new_label)

            print(" > Migrated label '%s' #%d to new label #%d" % (old_label.name, old_label.pk, new_label.pk))


class Migration(migrations.Migration):

    dependencies = [("msgs", "0009_label_migrate_pt1"), ("cases", "0022_delete_mesageaction")]

    operations = [
        migrations.AddField(model_name="case", name="new_labels", field=models.ManyToManyField(to="msgs.Label")),
        migrations.AddField(
            model_name="caseaction", name="new_label", field=models.ForeignKey(to="msgs.Label", null=True)
        ),
        migrations.AddField(model_name="partner", name="new_labels", field=models.ManyToManyField(to="msgs.Label")),
        migrations.RunPython(migrate_labels),
    ]
