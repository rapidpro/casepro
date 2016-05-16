# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from dash.utils import chunks
from django.db import migrations, models


def populate_reply_to(apps, schema_editor):
    Contact = apps.get_model('contacts', 'Contact')
    Message = apps.get_model('msgs', 'Message')
    Outgoing = apps.get_model('msgs', 'Outgoing')

    # ids of all contacts with outgoing messages
    contact_ids = list(Contact.objects.exclude(outgoing_messages=None).values_list('pk', flat=True))

    num_updated = 0

    for id_batch in chunks(contact_ids, 1000):
        contacts = Contact.objects.filter(pk__in=id_batch).prefetch_related('incoming_messages', 'outgoing_messages')

        for contact in contacts:
            timeline = list(contact.incoming_messages.all()) + list(contact.outgoing_messages.all())
            timeline = sorted(timeline, key=lambda x: x.created_on)

            prev_incoming = None
            for item in timeline:
                if isinstance(item, Message):
                    prev_incoming = item
                elif isinstance(item, Outgoing):
                    if prev_incoming:
                        item.reply_to.add(prev_incoming)
                    else:
                        print("WARNING: didn't find previous incoming message for outgoing message #%d" % item.pk)

        num_updated += len(id_batch)
        print("Updated %d of %d contacts with outgoing messages" % (num_updated, len(contact_ids)))


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0037_outgoing_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='outgoing',
            name='reply_to',
            field=models.ManyToManyField(related_name='replies', to='msgs.Message'),
        ),
        migrations.RunPython(populate_reply_to)
    ]
