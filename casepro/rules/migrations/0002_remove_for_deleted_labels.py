from django.db import migrations, models


def remove_rules_for_deleted_labels(apps, schema_editor):
    Label = apps.get_model("msgs", "Label")

    affected = Label.objects.filter(is_active=False).exclude(rule=None)

    for label in affected:
        rule = label.rule

        label.rule = None
        label.save(update_fields=("rule",))

        rule.delete()

    if affected:
        print("Removed rules for %d deleted labels" % len(affected))


class Migration(migrations.Migration):

    dependencies = [("rules", "0001_initial")]

    operations = [migrations.RunPython(remove_rules_for_deleted_labels)]
