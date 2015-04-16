from __future__ import absolute_import, unicode_literals

import json
import pytz

from dash.orgs.models import Org
from dash.utils import random_string
from django.contrib.auth.models import User
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import ugettext_lazy as _
from upartners.email import send_upartners_email
from upartners.labels.models import Label, SYSTEM_LABEL_FLAGGED


def parse_csv(csv, as_ints=False):
    """
    Parses a comma separated list of values as strings or integers
    """
    items = []
    for val in csv.split(','):
        if val:
            items.append(int(val) if as_ints else val.strip())
    return items


def message_as_json(msg, label_map):
    """
    Prepares a message (fetched from RapidPro) for JSON serialization
    """
    flagged = SYSTEM_LABEL_FLAGGED in msg.labels

    # convert label names to JSON label objects
    labels = [label_map[label_name].as_json() for label_name in msg.labels if label_name in label_map]

    return {'id': msg.id,
            'text': msg.text,
            'contact': msg.contact,
            'urn': msg.urn,
            'time': msg.created_on,
            'labels': labels,
            'flagged': flagged,
            'direction': msg.direction}


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
        return MessageExport.objects.create(org=org, created_by=user, search=json.dumps(search))

    def get_search(self):
        return json.loads(self.search)

    def do_export(self):
        """
        Does actual export. Called from a celery task as it may require a lot of API calls to grab all messages.
        """
        from xlwt import Workbook, XFStyle
        book = Workbook()

        date_style = XFStyle()
        date_style.num_format_str = 'DD-MM-YYYY HH:MM:SS'

        fields = ["Time", "Message ID", "Contact", "Text", "Unsolicited", "Flagged", "Labels"]
        label_map = {l.name: l for l in Label.get_all(self.org)}

        client = self.org.get_temba_client()
        search = self.get_search()
        pager = client.pager()
        all_messages = []

        while True:
            all_messages += client.get_messages(pager=pager, labels=search['labels'], direction='I',
                                                after=search['after'], before=search['before'],
                                                groups=search['groups'], text=search['text'], reverse=search['reverse'])
            if not pager.has_more():
                break

        messages_sheet_number = 1

        if not all_messages:
            book.add_sheet(unicode(_("Messages %d" % messages_sheet_number)))

        while all_messages:
            if len(all_messages) >= 65535:
                messages = all_messages[:65535]
                all_messages = all_messages[65535:]
            else:
                messages = all_messages
                all_messages = None

            current_sheet = book.add_sheet(unicode(_("Messages %d" % messages_sheet_number)))

            for col in range(len(fields)):
                field = fields[col]
                current_sheet.write(0, col, unicode(field))

            row = 1
            for msg in messages:
                created_on = msg.created_on.astimezone(pytz.utc).replace(tzinfo=None)
                flagged = SYSTEM_LABEL_FLAGGED in msg.labels
                labels = ', '.join([label_map[label_name].name for label_name in msg.labels if label_name in label_map])

                current_sheet.write(row, 0, created_on, date_style)
                current_sheet.write(row, 1, msg.id)
                current_sheet.write(row, 2, msg.contact)
                current_sheet.write(row, 3, msg.text)
                current_sheet.write(row, 4, 'Yes' if msg.type == 'I' else 'No')
                current_sheet.write(row, 5, 'Yes' if flagged else 'No')
                current_sheet.write(row, 6, labels)
                row += 1

            messages_sheet_number += 1

        temp = NamedTemporaryFile(delete=True)
        book.save(temp)
        temp.flush()

        filename = 'orgs/%d/message_exports/%s.xls' % (self.org_id, random_string(20))
        default_storage.save(filename, File(temp))

        self.filename = filename
        self.save(update_fields=('filename',))

        subject = "Your messages export is ready"
        download_url = 'https://%s%s' % (settings.HOSTNAME, reverse('home.messageexport_read', args=[self.pk]))

        # force a gc
        import gc
        gc.collect()

        send_upartners_email(self.created_by.username, subject, 'home/email/message_export', dict(link=download_url))
