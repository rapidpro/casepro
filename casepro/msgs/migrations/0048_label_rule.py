# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def create_label_rules(apps, schema_editor):
    Rule = apps.get_model("rules", "Rule")
    Label = apps.get_model("msgs", "Label")

    num_created = 0

    for label in Label.objects.all().select_related("org"):
        if label.tests:
            label.rule = Rule.objects.create(
                org=label.org, tests=label.tests, actions='[{"type": "label", "label": %d}]' % label.pk
            )
            label.save(update_fields=("rule",))
            num_created += 1

    if num_created:
        print("Converted %d label tests to rules" % num_created)


class Migration(migrations.Migration):

    dependencies = [("rules", "0001_initial"), ("msgs", "0047_outgoing_urn")]

    operations = [
        migrations.AddField(model_name="label", name="rule", field=models.OneToOneField(null=True, to="rules.Rule")),
        migrations.RunPython(create_label_rules),
    ]
