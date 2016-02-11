from __future__ import unicode_literals

import json
import pytz

from casepro.utils import JSONEncoder
from casepro.utils.email import send_email
from dash.orgs.models import Org
from dash.utils import chunks, random_string
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import ugettext_lazy as _
from temba_client.utils import parse_iso8601


SYSTEM_LABEL_FLAGGED = "Flagged"


class Message(models.Model):
    """
    A incoming message from the backend
    """
    TYPE_INBOX = 'I'
    TYPE_FLOW = 'F'

    TYPE_CHOICES = ((TYPE_INBOX, _("Inbox")), (TYPE_FLOW, _("Flow")))

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='incoming_messages')

    contact = models.ForeignKey('contacts.Contact')

    type = models.CharField(max_length=1)

    text = models.TextField(max_length=640, verbose_name=_("Text"))

    is_archived = models.BooleanField(default=False)

    created_on = models.DateTimeField()

    case = models.ForeignKey('cases.Case', null=True, related_name="incoming_messages")


class Outgoing(models.Model):
    """
    An outgoing message (i.e. broadcast) sent by a user
    """
    BULK_REPLY = 'B'
    CASE_REPLY = 'C'
    FORWARD = 'F'

    ACTIVITY_CHOICES = ((BULK_REPLY, _("Bulk Reply")), (CASE_REPLY, "Case Reply"), (FORWARD, _("Forward")))

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='outgoing_messages')

    activity = models.CharField(max_length=1, choices=ACTIVITY_CHOICES)

    text = models.TextField(max_length=640, null=True)

    broadcast_id = models.IntegerField()

    recipient_count = models.PositiveIntegerField()

    created_by = models.ForeignKey(User, related_name="outgoing_messages")

    created_on = models.DateTimeField(db_index=True)

    case = models.ForeignKey('cases.Case', null=True, related_name="outgoing_messages")

    @classmethod
    def create(cls, org, user, activity, text, urns, contacts, case=None):
        if not text:
            raise ValueError("Message text cannot be empty")

        broadcast = org.get_temba_client().create_broadcast(text=text, urns=urns, contacts=contacts)

        # TODO update RapidPro api to expose more accurate recipient_count
        recipient_count = len(broadcast.urns) + len(broadcast.contacts)

        return cls.objects.create(org=org,
                                  broadcast_id=broadcast.id,
                                  recipient_count=recipient_count,
                                  activity=activity, case=case,
                                  text=text,
                                  created_by=user,
                                  created_on=broadcast.created_on)

    def as_json(self):
        return {'id': self.pk,
                'text': self.text,
                'contact': self.case.contact.pk,
                'urn': None,
                'time': self.created_on,
                'labels': [],
                'flagged': False,
                'direction': 'O',
                'archived': False,
                'sender': self.created_by.as_json()}


class MessageExport(models.Model):
    """
    An export of messages
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='exports')

    search = models.TextField()

    filename = models.CharField(max_length=512)

    created_by = models.ForeignKey(User, related_name="exports")

    created_on = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create(cls, org, user, search):
        return MessageExport.objects.create(org=org, created_by=user, search=json.dumps(search, cls=JSONEncoder))

    def get_search(self):
        search = json.loads(self.search)
        if 'after' in search:
            search['after'] = parse_iso8601(search['after'])
        if 'before' in search:
            search['before'] = parse_iso8601(search['before'])
        return search

    def do_export(self):
        """
        Does actual export. Called from a celery task as it may require a lot of API calls to grab all messages.
        """
        from casepro.cases.models import RemoteMessage, Label
        from casepro.contacts.models import Field
        from xlwt import Workbook, XFStyle

        book = Workbook()

        date_style = XFStyle()
        date_style.num_format_str = 'DD-MM-YYYY HH:MM:SS'

        base_fields = ["Time", "Message ID", "Flagged", "Labels", "Text", "Contact"]
        contact_fields = [f.key for f in Field.get_all(self.org, visible=True)]
        all_fields = base_fields + contact_fields
        label_map = {l.name: l for l in Label.get_all(self.org)}

        client = self.org.get_temba_client()
        search = self.get_search()

        # fetch all messages to be exported
        messages = RemoteMessage.search(self.org, search, None)

        # extract all unique contacts in those messages
        contact_uuids = set()
        for msg in messages:
            contact_uuids.add(msg.contact)

        # fetch all contacts in batches of 25 and organize by UUID
        contacts_by_uuid = {}
        for uuid_chunk in chunks(list(contact_uuids), 25):
            for contact in client.get_contacts(uuids=uuid_chunk):
                contacts_by_uuid[contact.uuid] = contact

        def add_sheet(num):
            sheet = book.add_sheet(unicode(_("Messages %d" % num)))
            for col in range(len(all_fields)):
                field = all_fields[col]
                sheet.write(0, col, unicode(field))
            return sheet

        # even if there are no messages - still add a sheet
        if not messages:
            add_sheet(1)
        else:
            sheet_number = 1
            for msg_chunk in chunks(messages, 65535):
                current_sheet = add_sheet(sheet_number)

                row = 1
                for msg in msg_chunk:
                    created_on = msg.created_on.astimezone(pytz.utc).replace(tzinfo=None)
                    flagged = SYSTEM_LABEL_FLAGGED in msg.labels
                    labels = ', '.join([label_map[l_name].name for l_name in msg.labels if l_name in label_map])
                    contact = contacts_by_uuid.get(msg.contact, None)  # contact may no longer exist in RapidPro

                    current_sheet.write(row, 0, created_on, date_style)
                    current_sheet.write(row, 1, msg.id)
                    current_sheet.write(row, 2, 'Yes' if flagged else 'No')
                    current_sheet.write(row, 3, labels)
                    current_sheet.write(row, 4, msg.text)
                    current_sheet.write(row, 5, msg.contact)

                    for cf in range(len(contact_fields)):
                        if contact:
                            contact_field = contact_fields[cf]
                            current_sheet.write(row, 6 + cf, contact.fields.get(contact_field, None))
                        else:
                            current_sheet.write(row, 6 + cf, None)

                    row += 1

                sheet_number += 1

        temp = NamedTemporaryFile(delete=True)
        book.save(temp)
        temp.flush()

        filename = 'orgs/%d/message_exports/%s.xls' % (self.org.id, random_string(20))
        default_storage.save(filename, File(temp))

        self.filename = filename
        self.save(update_fields=('filename',))

        subject = "Your messages export is ready"
        download_url = settings.SITE_HOST_PATTERN % self.org.subdomain + reverse('msgs.messageexport_read', args=[self.pk])

        send_email(self.created_by.username, subject, 'msgs/email/message_export', dict(link=download_url))

        # force a gc
        import gc
        gc.collect()
