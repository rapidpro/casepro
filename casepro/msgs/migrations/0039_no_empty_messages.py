# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def delete_empty_messages(apps, schema_editor):
    Outgoing = apps.get_model('msgs', 'Outgoing')
    num_deleted = Outgoing.objects.filter(text=None).delete()

    if num_deleted:
        print("Deleted %d empty messages" % num_deleted)


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0038_outgoing_reply_to'),
    ]

    operations = [
        migrations.RunPython(delete_empty_messages)
    ]
