from __future__ import unicode_literals

import json
import pytz
import regex
import six

from casepro.contacts.models import Contact
from casepro.utils import JSONEncoder, normalize, parse_csv
from casepro.utils.email import send_email
from dash.orgs.models import Org
from dash.utils import chunks, random_string
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.timezone import now
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from temba_client.utils import parse_iso8601
from temba_client.exceptions import TembaException


SYSTEM_LABEL_FLAGGED = "Flagged"

# only show unlabelled messages newer than 2 weeks
DEFAULT_UNLABELLED_LIMIT_DAYS = 14


@python_2_unicode_compatible
class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    KEYWORD_MIN_LENGTH = 3

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='new_labels')

    uuid = models.CharField(max_length=36, unique=True)

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    description = models.CharField(verbose_name=_("Description"), max_length=255)

    keywords = models.CharField(verbose_name=_("Keywords"), max_length=1024, blank=True)

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    @classmethod
    def create(cls, org, name, description, keywords, partners, uuid=None):
        if not uuid:
            remote = cls.get_or_create_remote(org, name)
            uuid = remote.uuid

        label = cls.objects.create(uuid=uuid, org=org, name=name, description=description,
                                   keywords=','.join(keywords))
        label.partners.add(*partners)

        return label

    @classmethod
    def get_or_create_remote(cls, org, name):
        client = org.get_temba_client()
        temba_labels = client.get_labels(name=name)  # gets all partial name matches
        temba_labels = [l for l in temba_labels if l.name.lower() == name.lower()]

        if temba_labels:
            return temba_labels[0]
        else:
            return client.create_label(name)

    @classmethod
    def get_all(cls, org, user=None):
        if not user or user.can_administer(org):
            return cls.objects.filter(org=org, is_active=True)

        partner = user.get_partner()
        return partner.get_labels() if partner else cls.objects.none()

    @classmethod
    def get_keyword_map(cls, org):
        """
        Gets a map of all keywords to their corresponding labels
        :param org: the org
        :return: map of keywords to labels
        """
        labels_by_keyword = {}
        for label in Label.get_all(org):
            for keyword in label.get_keywords():
                labels_by_keyword[keyword] = label
        return labels_by_keyword

    def update_name(self, name):
        # try to update remote label
        try:
            client = self.org.get_temba_client()
            client.update_label(uuid=self.uuid, name=name)
        except TembaException:
            # rename may fail if remote label no longer exists or new name conflicts with other remote label
            pass

        self.name = name
        self.save()

    def get_keywords(self):
        return parse_csv(self.keywords)

    def get_partners(self):
        return self.partners.filter(is_active=True)

    def release(self):
        self.is_active = False
        self.save(update_fields=('is_active',))

    def as_json(self):
        return {'id': self.pk, 'name': self.name, 'count': getattr(self, 'count', None)}

    @classmethod
    def is_valid_keyword(cls, keyword):
        return len(keyword) >= cls.KEYWORD_MIN_LENGTH and regex.match(r'^\w[\w\- ]*\w$', keyword)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Message(models.Model):
    """
    A incoming message from the backend
    """
    TYPE_INBOX = 'I'
    TYPE_FLOW = 'F'

    TYPE_CHOICES = ((TYPE_INBOX, _("Inbox")), (TYPE_FLOW, _("Flow")))

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='incoming_messages')

    backend_id = models.IntegerField(unique=True, help_text=_("Backend identifier for this message"))

    contact = models.ForeignKey('contacts.Contact')

    type = models.CharField(max_length=1)

    text = models.TextField(max_length=640, verbose_name=_("Text"))

    is_handled = models.BooleanField(default=False)

    is_archived = models.BooleanField(default=False)

    created_on = models.DateTimeField()

    case = models.ForeignKey('cases.Case', null=True, related_name="incoming_messages")

    def auto_label(self, labels_by_keyword):
        """
        Applies the auto-label matcher to this message
        :param labels_by_keyword: a map of labels by each keyword
        :return: the set of matching labels
        """
        norm_text = normalize(self.text)
        matches = set()

        for keyword, label in six.iteritems(labels_by_keyword):
            if regex.search(r'\b' + keyword + r'\b', norm_text, flags=regex.IGNORECASE | regex.UNICODE | regex.V0):
                matches.add(label)

        return matches

    def __str__(self):
        return self.text if self.text else self.pk


class MessageAction(models.Model):
    """
    An action performed on a set of messages
    """
    FLAG = 'F'
    UNFLAG = 'N'
    LABEL = 'L'
    UNLABEL = 'U'
    ARCHIVE = 'A'
    RESTORE = 'R'

    ACTION_CHOICES = ((FLAG, _("Flag")),
                      (UNFLAG, _("Un-flag")),
                      (LABEL, _("Label")),
                      (UNLABEL, _("Remove Label")),
                      (ARCHIVE, _("Archive")),
                      (RESTORE, _("Restore")))

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='message_actions')

    messages = ArrayField(models.IntegerField())

    action = models.CharField(max_length=1, choices=ACTION_CHOICES)

    created_by = models.ForeignKey(User, related_name="message_actions")

    created_on = models.DateTimeField(auto_now_add=True)

    label = models.ForeignKey(Label, null=True)

    @classmethod
    def create(cls, org, user, message_ids, action, label=None):
        MessageAction.objects.create(org=org, messages=message_ids, action=action, created_by=user, label=label)

    @classmethod
    def get_by_message(cls, org, message_id):
        return cls.objects.filter(org=org, messages__contains=[message_id]).select_related('created_by', 'label')

    def as_json(self):
        return {'id': self.pk,
                'action': self.action,
                'created_by': self.created_by.as_json(),
                'created_on': self.created_on,
                'label': self.label.as_json() if self.label else None}


class RemoteMessage(object):
    """
    A pseudo-model for messages which are always fetched from RapidPro.
    """
    @staticmethod
    def bulk_flag(org, user, message_ids):
        if message_ids:
            client = org.get_temba_client()
            client.label_messages(message_ids, label=SYSTEM_LABEL_FLAGGED)

            MessageAction.create(org, user, message_ids, MessageAction.FLAG)

    @staticmethod
    def bulk_unflag(org, user, message_ids):
        if message_ids:
            client = org.get_temba_client()
            client.unlabel_messages(message_ids, label=SYSTEM_LABEL_FLAGGED)

            MessageAction.create(org, user, message_ids, MessageAction.UNFLAG)

    @staticmethod
    def bulk_label(org, user, message_ids, label):
        if message_ids:
            client = org.get_temba_client()
            client.label_messages(message_ids, label_uuid=label.uuid)

            MessageAction.create(org, user, message_ids, MessageAction.LABEL, label)

    @staticmethod
    def bulk_unlabel(org, user, message_ids, label):
        if message_ids:
            client = org.get_temba_client()
            client.unlabel_messages(message_ids, label_uuid=label.uuid)

            MessageAction.create(org, user, message_ids, MessageAction.UNLABEL, label)

    @staticmethod
    def bulk_archive(org, user, message_ids):
        if message_ids:
            client = org.get_temba_client()
            client.archive_messages(message_ids)

            MessageAction.create(org, user, message_ids, MessageAction.ARCHIVE)

    @staticmethod
    def bulk_restore(org, user, message_ids):
        if message_ids:
            client = org.get_temba_client()
            client.unarchive_messages(message_ids)

            MessageAction.create(org, user, message_ids, MessageAction.RESTORE)

    @classmethod
    def update_labels(cls, msg, org, user, labels):
        """
        Updates all this message's labels to the given set, creating label and unlabel actions as necessary
        """
        from casepro.cases.models import Label

        current_labels = Label.get_all(org, user).filter(name__in=msg.labels)

        add_labels = [l for l in labels if l not in current_labels]
        rem_labels = [l for l in current_labels if l not in labels]

        for label in add_labels:
            cls.bulk_label(org, user, [msg.id], label)
        for label in rem_labels:
            cls.bulk_unlabel(org, user, [msg.id], label)

    @classmethod
    def annotate_with_sender(cls, org, messages):
        """
        Look for outgoing records for the given messages and annotate them with their sender if one exists
        """
        broadcast_ids = set([m.broadcast for m in messages if m.broadcast])
        outgoings = Outgoing.objects.filter(org=org, broadcast_id__in=broadcast_ids)
        broadcast_to_outgoing = {out.broadcast_id: out for out in outgoings}

        for msg in messages:
            outgoing = broadcast_to_outgoing.get(msg.broadcast, None)
            msg.sender = outgoing.created_by if outgoing else None

    @staticmethod
    def search(org, search, pager):
        """
        Search for labelled messages in RapidPro
        """
        if not search['labels']:  # no access to un-labelled messages
            return []

        # all queries either filter by at least one label, or exclude all labels using - prefix
        labelled_search = bool([l for l in search['labels'] if not l.startswith('-')])

        # put limit on how far back we fetch unlabelled messages because there are lots of those
        if not labelled_search and not search['after']:
            limit_days = getattr(settings, 'UNLABELLED_LIMIT_DAYS', DEFAULT_UNLABELLED_LIMIT_DAYS)
            search['after'] = now() - timedelta(days=limit_days)

        # *** TEMPORARY *** fix to disable the Unlabelled view which is increasingly not performant, until the larger
        # message store refactor is complete. This removes any label exclusions from the search.
        search['labels'] = [l for l in search['labels'] if not l.startswith('-')]

        client = org.get_temba_client()
        messages = client.get_messages(pager=pager, text=search['text'], labels=search['labels'],
                                       contacts=search['contacts'], groups=search['groups'],
                                       direction='I', _types=search['types'], archived=search['archived'],
                                       after=search['after'], before=search['before'])

        # annotate messages with contacts (if they exist). This becomes a lot easier with local messages.
        contact_uuids = [m.contact for m in messages]
        contacts = Contact.objects.filter(org=org, uuid__in=contact_uuids)
        contacts_by_uuid = {c.uuid: c for c in contacts}
        for message in messages:
            contact = contacts_by_uuid.get(message.contact)
            if contact:
                message.contact = {'uuid': contact.uuid, 'is_stub': contact.is_stub}
            else:
                message.contact = {'uuid': message.contact, 'is_stub': True}

        return messages

    @staticmethod
    def as_json(msg, label_map):
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
                'direction': 'I' if msg.direction in ('I', 'in') else 'O',
                'archived': msg.archived,
                'sender': msg.sender.as_json() if getattr(msg, 'sender', None) else None}


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
        from casepro.cases.models import Label
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
            contact_uuids.add(msg.contact['uuid'])

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
                    contact = contacts_by_uuid.get(msg.contact['uuid'])  # contact may no longer exist in RapidPro

                    current_sheet.write(row, 0, created_on, date_style)
                    current_sheet.write(row, 1, msg.id)
                    current_sheet.write(row, 2, 'Yes' if flagged else 'No')
                    current_sheet.write(row, 3, labels)
                    current_sheet.write(row, 4, msg.text)
                    current_sheet.write(row, 5, contact.uuid)

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
