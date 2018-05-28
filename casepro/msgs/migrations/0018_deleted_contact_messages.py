# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def fix_deleted_contact_messages(apps, schema_editor):
    Message = apps.get_model("msgs", "Message")
    num_effected = Message.objects.filter(contact__is_active=False).update(is_handled=True, is_active=False)
    if num_effected:
        print("Fixed %d messages belonging to deleted contacts" % num_effected)


class Migration(migrations.Migration):

    dependencies = [("msgs", "0017_auto_20160301_1430")]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="contact",
            field=models.ForeignKey(related_name="incoming_messages", to="contacts.Contact"),
        ),
        migrations.RunPython(fix_deleted_contact_messages),
    ]
