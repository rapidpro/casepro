# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def delete_empty_messages(apps, schema_editor):
    Outgoing = apps.get_model("msgs", "Outgoing")

    empties = Outgoing.objects.filter(text=None)
    num_empties = len(empties)

    empties.delete()

    if num_empties:
        print("Deleted %d empty messages" % num_empties)


class Migration(migrations.Migration):

    dependencies = [("msgs", "0037_outgoing_indexes")]

    operations = [migrations.RunPython(delete_empty_messages)]
