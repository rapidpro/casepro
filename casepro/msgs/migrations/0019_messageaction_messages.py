# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def populate_messages_new(apps, schema_editor):
    Message = apps.get_model("msgs", "Message")
    MessageAction = apps.get_model("msgs", "MessageAction")

    actions = list(MessageAction.objects.all())

    for action in actions:
        remote_backend_ids = list(action.messages)

        local_messages = list(Message.objects.filter(backend_id__in=remote_backend_ids))
        local_backend_ids = {m.backend_id for m in local_messages}

        action.messages_new.add(*local_messages)

        missing_backend_ids = [i for i in remote_backend_ids if i not in local_backend_ids]

        for missing_id in missing_backend_ids:
            print("Couldn't find message #%d for action #%d in org #%d" % (missing_id, action.pk, action.org_id))

    if actions:
        print("Migrated %d actions" % len(actions))


class Migration(migrations.Migration):

    dependencies = [("msgs", "0018_deleted_contact_messages")]

    operations = [
        migrations.AddField(
            model_name="messageaction",
            name="messages_new",
            field=models.ManyToManyField(related_name="actions", to="msgs.Message"),
        ),
        migrations.RunPython(populate_messages_new),
        migrations.RemoveField(model_name="messageaction", name="messages"),
    ]
