# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def delete_null_values(apps, schema_editor):
    Value = apps.get_model("contacts", "Value")
    Value.objects.filter(string_value=None).delete()


class Migration(migrations.Migration):

    dependencies = [("contacts", "0014_auto_20160212_0927")]

    operations = [
        migrations.RunPython(delete_null_values),
        migrations.AlterField(
            model_name="value",
            name="string_value",
            field=models.TextField(
                help_text="The string value or string representation of this value", max_length=640
            ),
        ),
    ]
