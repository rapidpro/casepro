from __future__ import unicode_literals

import json
import pytz
import regex
import six

from casepro.backend import get_backend
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
from redis_cache import get_redis_connection
from temba_client.utils import parse_iso8601


# only show unlabelled messages newer than 2 weeks
DEFAULT_UNLABELLED_LIMIT_DAYS = 14

SAVE_CONTACT_ATTR = '__data__contact'
SAVE_LABELS_ATTR = '__data__labels'

LABEL_LOCK_KEY = 'lock:label:%d:%s'
MESSAGE_LOCK_KEY = 'lock:message:%d:%d'


@python_2_unicode_compatible
class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    KEYWORD_MIN_LENGTH = 3

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='labels')

    uuid = models.CharField(max_length=36, unique=True)

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    description = models.CharField(verbose_name=_("Description"), null=True, max_length=255)

    keywords = models.CharField(verbose_name=_("Keywords"), null=True, blank=True, max_length=1024)

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    @classmethod
    def create(cls, org, name, description, keywords):
        remote_uuid = get_backend().create_label(org, name)

        return cls.objects.create(org=org,
                                  uuid=remote_uuid,
                                  name=name,
                                  description=description,
                                  keywords=','.join(keywords))

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

    @classmethod
    def lock(cls, org, uuid):
        return get_redis_connection().lock(LABEL_LOCK_KEY % (org.pk, uuid), timeout=60)

    def get_keywords(self):
        return parse_csv(self.keywords) if self.keywords else []

    def get_partners(self):
        return self.partners.filter(is_active=True)

    def release(self):
        self.is_active = False
        self.save(update_fields=('is_active',))

    def as_json(self):
        return {'id': self.pk, 'uuid': self.uuid, 'name': self.name}

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

    contact = models.ForeignKey(Contact, related_name='incoming_messages')

    type = models.CharField(max_length=1)

    text = models.TextField(max_length=640, verbose_name=_("Text"))

    labels = models.ManyToManyField(Label, help_text=_("Labels assigned to this message"), related_name='messages')

    is_flagged = models.BooleanField(default=False)

    is_archived = models.BooleanField(default=False)

    created_on = models.DateTimeField()

    is_handled = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    case = models.ForeignKey('cases.Case', null=True, related_name="incoming_messages")

    def __init__(self, *args, **kwargs):
        if SAVE_CONTACT_ATTR in kwargs:
            setattr(self, SAVE_CONTACT_ATTR, kwargs.pop(SAVE_CONTACT_ATTR))
        if SAVE_LABELS_ATTR in kwargs:
            setattr(self, SAVE_LABELS_ATTR, kwargs.pop(SAVE_LABELS_ATTR))

        super(Message, self).__init__(*args, **kwargs)

    @classmethod
    def get_unhandled(cls, org):
        return cls.objects.filter(org=org, is_handled=False)

    @classmethod
    def lock(cls, org, backend_id):
        return get_redis_connection().lock(MESSAGE_LOCK_KEY % (org.pk, backend_id), timeout=60)

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

    def release(self):
        """
        Deletes this message, removing it from any labels (only callable by sync)
        """
        self.labels.clear()

        self.is_active = False
        self.save(update_fields=('is_active',))

    def update_labels(self, user, labels):
        """
        Updates this message's labels to match the given set, creating label and unlabel actions as necessary
        """
        with self.lock(self.org, self.backend_id):
            current_labels = set(self.labels.all())

            add_labels = [l for l in labels if l not in current_labels]
            rem_labels = [l for l in current_labels if l not in labels]

            for label in add_labels:
                self.bulk_label(self.org, user, [self], label)
            for label in rem_labels:
                self.bulk_unlabel(self.org, user, [self], label)

    @staticmethod
    def bulk_flag(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(is_flagged=True)

            get_backend().flag_messages(org, messages)

            MessageAction.create(org, user, [m.backend_id for m in messages], MessageAction.FLAG)

    @staticmethod
    def bulk_unflag(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(is_flagged=False)

            get_backend().unflag_messages(org, messages)

            MessageAction.create(org, user, [m.backend_id for m in messages], MessageAction.UNFLAG)

    @staticmethod
    def bulk_label(org, user, messages, label):
        messages = list(messages)
        if messages:
            for msg in messages:
                msg.labels.add(label)

            get_backend().label_messages(org, messages, label)

            MessageAction.create(org, user, [m.backend_id for m in messages], MessageAction.LABEL, label)

    @staticmethod
    def bulk_unlabel(org, user, messages, label):
        messages = list(messages)
        if messages:
            for msg in messages:
                msg.labels.remove(label)

            get_backend().unlabel_messages(org, messages, label)

            MessageAction.create(org, user, [m.backend_id for m in messages], MessageAction.UNLABEL, label)

    @staticmethod
    def bulk_archive(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(is_archived=True)

            get_backend().archive_messages(org, messages)

            MessageAction.create(org, user, [m.backend_id for m in messages], MessageAction.ARCHIVE)

    @staticmethod
    def bulk_restore(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(is_archived=False)

            get_backend().restore_messages(org, messages)

            MessageAction.create(org, user, [m.backend_id for m in messages], MessageAction.RESTORE)

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
    A pseudo-model for messages which are always fetched from RapidPro. All of these methods will be replaced by new
    methods in the Message class which operate both locally and remotely.
    """
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

        client = org.get_temba_client(api_version=1)
        backend_messages = client.get_messages(pager=pager, text=search['text'], labels=search['labels'],
                                               contacts=search['contacts'], groups=search['groups'],
                                               direction='I', _types=search['types'], archived=search['archived'],
                                               after=search['after'], before=search['before'])

        # only show remote messages which match a local handled message. This is stop users actioning or casing messages
        # which aren't synced. Needed until refactor is complete... when we'll actually be searching against local
        # handled messages
        backend_ids = [m.id for m in backend_messages]
        local_messages = org.incoming_messages.filter(backend_id__in=backend_ids, is_handled=True)
        local_messages = list(local_messages.select_related('contact'))
        local_by_backend_id = {m.backend_id: m for m in local_messages}

        annotated = []
        for backend_message in backend_messages:
            local_message = local_by_backend_id.get(backend_message.id)
            if local_message:
                backend_message.contact = local_message.contact.as_json()
                backend_message.visibility = ('archived' if backend_message.archived else 'visible')
                annotated.append(backend_message)

        return annotated

    @staticmethod
    def as_json(msg, label_map):
        """
        Prepares a message (fetched from RapidPro) for JSON serialization
        """
        from casepro.backend.rapidpro import SYSTEM_LABEL_FLAGGED

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
                'archived': msg.visibility == 'archived',
                'sender': msg.sender.as_json() if getattr(msg, 'sender', None) else None}


@python_2_unicode_compatible
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

    def __str__(self):
        return self.text


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
        from casepro.backend.rapidpro import SYSTEM_LABEL_FLAGGED
        from xlwt import Workbook, XFStyle

        book = Workbook()

        date_style = XFStyle()
        date_style.num_format_str = 'DD-MM-YYYY HH:MM:SS'

        base_fields = ["Time", "Message ID", "Flagged", "Labels", "Text", "Contact"]
        contact_fields = [f.key for f in Field.get_all(self.org, visible=True)]
        all_fields = base_fields + contact_fields
        label_map = {l.name: l for l in Label.get_all(self.org)}

        search = self.get_search()

        # fetch all messages to be exported
        messages = RemoteMessage.search(self.org, search, None)

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

                    current_sheet.write(row, 0, created_on, date_style)
                    current_sheet.write(row, 1, msg.id)
                    current_sheet.write(row, 2, 'Yes' if flagged else 'No')
                    current_sheet.write(row, 3, labels)
                    current_sheet.write(row, 4, msg.text)
                    current_sheet.write(row, 5, msg.contact['uuid'])

                    # TODO after refactor, .search() should return Message objects with contacts
                    contact = Contact.objects.filter(uuid=msg.contact['uuid']).first()
                    fields = contact.get_fields() if contact else {}

                    for cf in range(len(contact_fields)):
                        contact_field = contact_fields[cf]
                        current_sheet.write(row, 6 + cf, fields.get(contact_field, None))

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
