from __future__ import absolute_import, unicode_literals

import json
import pytz

from dash.orgs.models import Org
from dash.utils import get_obj_cacheable, random_string, chunks, intersection
from datetime import date
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from temba.base import TembaNoSuchObjectError
from upartners.email import send_email
from . import parse_csv, truncate, SYSTEM_LABEL_FLAGGED


class Group(models.Model):
    """
    Corresponds to a RapidPro contact group, used for filtering messages
    """
    uuid = models.CharField(max_length=36, unique=True)

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='groups')

    name = models.CharField(verbose_name=_("Name"), max_length=128, blank=True,
                            help_text=_("Name of this filter group"))

    is_active = models.BooleanField(default=True, help_text="Whether this filter group is active")

    @classmethod
    def create(cls, org, name, uuid):
        return cls.objects.create(org=org, name=name, uuid=uuid)

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org, is_active=True)

    @classmethod
    def fetch_sizes(cls, org, groups):
        group_by_uuid = {g.uuid: g for g in groups}
        if group_by_uuid:
            temba_groups = org.get_temba_client().get_groups(uuids=group_by_uuid.keys())
            size_by_uuid = {l.uuid: l.size for l in temba_groups}
        else:
            size_by_uuid = {}

        return {l: size_by_uuid[l.uuid] if l.uuid in size_by_uuid else 0 for l in groups}

    def get_size(self):
        return get_obj_cacheable(self, '_size', lambda: self.fetch_sizes(self.org, [self])[self])

    @classmethod
    def update_groups(cls, org, group_uuids):
        """
        Updates an org's filter groups based on the selected groups UUIDs
        """
        # de-activate groups not included
        org.groups.exclude(uuid__in=group_uuids).update(is_active=False)

        # fetch group details
        groups = org.get_temba_client().get_groups(uuids=group_uuids)
        group_names = {group.uuid: group.name for group in groups}

        for group_uuid in group_uuids:
            existing = org.groups.filter(uuid=group_uuid).first()
            if existing:
                existing.name = group_names[group_uuid]
                existing.is_active = True
                existing.save()
            else:
                cls.create(org, group_names[group_uuid], group_uuid)

    def as_json(self):
        return {'id': self.pk, 'name': self.name, 'uuid': self.uuid}

    def __unicode__(self):
        return self.name


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

        base_fields = ["Time", "Message ID", "Flagged", "Labels", "Text", "Contact"]
        contact_fields = self.org.get_contact_fields()
        all_fields = base_fields + contact_fields
        label_map = {l.name: l for l in Label.get_all(self.org)}

        client = self.org.get_temba_client()
        search = self.get_search()
        pager = client.pager()
        all_messages = []

        # fetch all messages to be exported
        while True:
            all_messages += Message.search(client, search, pager)
            if not pager.has_more():
                break

        # extract all unique contacts in those messages
        contact_uuids = set()
        for msg in all_messages:
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
        if not all_messages:
            add_sheet(1)
        else:
            sheet_number = 1
            for msg_chunk in chunks(all_messages, 65535):
                current_sheet = add_sheet(sheet_number)

                row = 1
                for msg in msg_chunk:
                    created_on = msg.created_on.astimezone(pytz.utc).replace(tzinfo=None)
                    flagged = SYSTEM_LABEL_FLAGGED in msg.labels
                    labels = ', '.join([label_map[label_name].name for label_name in msg.labels if label_name in label_map])
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

        filename = 'orgs/%d/message_exports/%s.xls' % (self.org_id, random_string(20))
        default_storage.save(filename, File(temp))

        self.filename = filename
        self.save(update_fields=('filename',))

        subject = "Your messages export is ready"
        download_url = 'https://%s%s' % (settings.HOSTNAME, reverse('cases.messageexport_read', args=[self.pk]))

        # force a gc
        import gc
        gc.collect()

        send_email(self.created_by.username, subject, 'cases/email/message_export', dict(link=download_url))


class Partner(models.Model):
    """
    Corresponds to a partner organization
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='partners')

    name = models.CharField(verbose_name=_("Name"), max_length=128,
                            help_text=_("Name of this partner organization"))

    is_active = models.BooleanField(default=True, help_text="Whether this partner is active")

    @classmethod
    def create(cls, org, name):
        return cls.objects.create(org=org, name=name)

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org, is_active=True)

    def get_labels(self):
        return self.labels.filter(is_active=True)

    def get_users(self):
        return User.objects.filter(profile__partner=self, is_active=True)

    def get_managers(self):
        return self.get_users().filter(org_editors=self.org_id)

    def get_analysts(self):
        return self.get_users().filter(org_viewers=self.org_id)

    def as_json(self):
        return {'id': self.pk, 'name': self.name}

    def __unicode__(self):
        return self.name


class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='labels')

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    description = models.CharField(verbose_name=_("Description"), max_length=255)

    keywords = models.CharField(verbose_name=_("Keywords"), max_length=1024, blank=True)

    partners = models.ManyToManyField(Partner, related_name='labels',
                                      help_text=_("Partner organizations who can access messages with this label"))

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    @classmethod
    def create(cls, org, name, description, keywords, partners):
        label = cls.objects.create(org=org, name=name, description=description, keywords=','.join(keywords))
        label.partners.add(*partners)
        return label

    @classmethod
    def get_all(cls, org, user=None):
        if not user or user.is_admin_for(org):
            return cls.objects.filter(org=org, is_active=True)

        partner = user.get_partner()
        return partner.get_labels() if partner else cls.none()

    @classmethod
    def get_message_counts(cls, org, labels):
        label_by_name = {l.name: l for l in labels}
        if label_by_name:
            temba_labels = org.get_temba_client().get_labels()
            counts_by_name = {l.name: l.count for l in temba_labels if l.name}
        else:
            counts_by_name = {}

        return {l: counts_by_name.get(l.name, 0) for l in labels}

    @classmethod
    def get_case_counts(cls, labels, closed=False):
        if not closed:
            qs = labels.filter(cases__closed_on=None)
        else:
            # can't use exclude with the annotation below
            qs = labels.filter(cases__closed_on__gt=date(1970, 1, 1))

        counts_by_label = {l: l.num_cases for l in qs.annotate(num_cases=Count('cases'))}

        return {l: counts_by_label.get(l, 0) for l in labels}

    def get_keywords(self):
        return parse_csv(self.keywords)

    def get_partners(self):
        return self.partners.filter(is_active=True)

    def release(self):
        self.is_active = False
        self.save(update_fields=('is_active',))

    def as_json(self):
        return {'id': self.pk, 'name': self.name, 'count': getattr(self, 'count', None)}

    def __unicode__(self):
        return self.name


class case_action(object):
    """
    Helper decorator for cae action methods that should check the user is allowed to update the case
    """
    def __init__(self, require_update=True):
        self.require_update = require_update

    def __call__(self, func):
        def wrapped(case, user, *args, **kwargs):
            if not case.accessible_by(user, update=self.require_update):
                raise PermissionDenied()
            func(case, user, *args, **kwargs)
        return wrapped


class Case(models.Model):
    """
    A case between a partner organization and a contact
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='cases')

    labels = models.ManyToManyField(Label, verbose_name=_("Labels"), related_name='cases')

    assignee = models.ForeignKey(Partner, related_name="cases")

    contact_uuid = models.CharField(max_length=36, db_index=True)

    message_id = models.IntegerField(unique=True)

    message_on = models.DateTimeField(help_text="When initial message was sent")

    summary = models.CharField(verbose_name=_("Summary"), max_length=255)

    opened_on = models.DateTimeField(auto_now_add=True,
                                     help_text="When this case was opened")

    closed_on = models.DateTimeField(null=True,
                                     help_text="When this case was closed")

    @classmethod
    def get_all(cls, org, labels=None):
        qs = cls.objects.filter(org=org)
        if labels:
            qs = qs.filter(labels=labels).distinct()

        return qs.prefetch_related('labels')

    @classmethod
    def get_open(cls, org, labels=None):
        return cls.get_all(org, labels).filter(closed_on=None)

    @classmethod
    def get_closed(cls, org, labels=None):
        return cls.get_all(org, labels).exclude(closed_on=None)

    @classmethod
    def get_for_contact(cls, org, contact_uuid):
        return cls.get_all(org).filter(contact_uuid=contact_uuid)

    @classmethod
    def get_open_for_contact_on(cls, org, contact_uuid, dt):
        qs = cls.get_for_contact(org, contact_uuid)
        return qs.filter(opened_on__lt=dt).filter(Q(closed_on=None) | Q(closed_on__gt=dt))

    def get_labels(self):
        return self.labels.filter(is_active=True)

    @classmethod
    def open(cls, org, user, labels, partner, message, archive_messages=True):
        # check for open case with this contact
        if cls.get_open_for_contact_on(org, message.contact, timezone.now()).exists():
            raise ValueError("Contact already has open case")

        summary = truncate(message.text, 255)
        case = cls.objects.create(org=org, assignee=partner, contact_uuid=message.contact,
                                  summary=summary, message_id=message.id, message_on=message.created_on)
        case.labels.add(*labels)

        CaseAction.create(case, user, CaseAction.OPEN, assignee=partner)

        # archive messages and subsequent messages from same contact
        if archive_messages:
            client = org.get_temba_client()
            messages = client.get_messages(contacts=[message.contact], direction='I', statuses=['H'], _types=['I'],
                                           after=message.created_on)
            message_ids = [m.id for m in messages]
            client.archive_messages(messages=message_ids)

        return case

    @case_action(require_update=False)
    def note(self, user, note):
        CaseAction.create(self, user, CaseAction.NOTE, note=note)

    @case_action()
    def close(self, user, note=None):
        self.closed_on = timezone.now()
        self.save(update_fields=('closed_on',))

        CaseAction.create(self, user, CaseAction.CLOSE, note=note)

    @case_action()
    def reopen(self, user, note=None):
        self.closed_on = None
        self.save(update_fields=('closed_on',))

        CaseAction.create(self, user, CaseAction.REOPEN, note=note)

    @case_action()
    def reassign(self, user, partner, note=None):
        self.assignee = partner
        self.save(update_fields=('assignee',))

        CaseAction.create(self, user, CaseAction.REASSIGN, assignee=partner, note=note)

    @case_action()
    def label(self, user, label):
        self.labels.add(label)

        CaseAction.create(self, user, CaseAction.LABEL, label=label)

    @case_action()
    def unlabel(self, user, label):
        self.labels.remove(label)

        CaseAction.create(self, user, CaseAction.UNLABEL, label=label)

    def update_labels(self, user, labels):
        """
        Updates all this cases's labels to the given set, creating label and unlabel actions as necessary
        """
        current_labels = self.labels.all()

        add_labels = [l for l in labels if l not in current_labels]
        rem_labels = [l for l in current_labels if l not in labels]

        for label in add_labels:
            self.label(user, label)
        for label in rem_labels:
            self.unlabel(user, label)

    def fetch_contact(self):
        try:
            return self.org.get_temba_client().get_contact(self.contact_uuid)
        except TembaNoSuchObjectError:
            return None  # always a chance that the contact has been deleted in RapidPro

    def accessible_by(self, user, update=False):
        """
        A user can view a case if one of these conditions is met:
            1) they are an administrator for the case org
            2) their partner org is assigned to the case
            3) their partner org can view a label assigned to the case

        They can additionally update the case if 1) or 2) is true
        """
        if user.is_admin_for(self.org):
            return True

        if user.profile.partner == self.assignee:
            return True

        return not update and intersection(self.get_labels(), user.profile.partner.get_labels())

    def as_json(self):
        return {'id': self.pk,
                'assignee': self.assignee.as_json(),
                'labels': [l.as_json() for l in self.get_labels()],
                'summary': self.summary,
                'opened_on': self.opened_on,
                'is_closed': self.closed_on is not None}

    def __unicode__(self):
        return '#%d' % self.pk


class CaseAction(models.Model):
    """
    An action performed on a case
    """
    OPEN = 'O'
    NOTE = 'N'
    REASSIGN = 'A'
    LABEL = 'L'
    UNLABEL = 'U'
    CLOSE = 'C'
    REOPEN = 'R'

    ACTION_CHOICES = ((OPEN, _("Open")),
                      (NOTE, _("Add Note")),
                      (REASSIGN, _("Reassign")),
                      (LABEL, _("Label")),
                      (UNLABEL, _("Remove Label")),
                      (CLOSE, _("Close")),
                      (REOPEN, _("Reopen")))

    case = models.ForeignKey(Case, related_name="actions")

    action = models.CharField(max_length=1, choices=ACTION_CHOICES)

    created_by = models.ForeignKey(User, related_name="case_actions")

    created_on = models.DateTimeField(auto_now_add=True)

    assignee = models.ForeignKey(Partner, null=True, related_name="case_actions")

    label = models.ForeignKey(Label, null=True)

    note = models.CharField(null=True, max_length=1024)

    @classmethod
    def create(cls, case, user, action, assignee=None, label=None, note=None):
        CaseAction.objects.create(case=case, action=action, created_by=user, assignee=assignee, label=label, note=note)

    def as_json(self):
        return {'id': self.pk,
                'action': self.action,
                'created_by': {'id': self.created_by.pk, 'name': self.created_by.get_full_name()},
                'created_on': self.created_on,
                'assignee': self.assignee.as_json() if self.assignee else None,
                'label': self.label.as_json() if self.label else None,
                'note': self.note}


class Message(object):
    """
    A pseudo-model for messages which are always fetched from RapidPro.
    """
    @staticmethod
    def bulk_flag(org, user, message_ids):
        client = org.get_temba_client()
        client.label_messages(message_ids, label=SYSTEM_LABEL_FLAGGED)

        MessageAction.create(org, user, message_ids, MessageAction.FLAG)

    @staticmethod
    def bulk_unflag(org, user, message_ids):
        client = org.get_temba_client()
        client.unlabel_messages(message_ids, label=SYSTEM_LABEL_FLAGGED)

        MessageAction.create(org, user, message_ids, MessageAction.UNFLAG)

    @staticmethod
    def bulk_label(org, user, message_ids, label):
        client = org.get_temba_client()
        client.label_messages(message_ids, label=label.name)

        MessageAction.create(org, user, message_ids, MessageAction.LABEL, label)

    @staticmethod
    def bulk_archive(org, user, message_ids):
        client = org.get_temba_client()
        client.archive_messages(message_ids)

        MessageAction.create(org, user, message_ids, MessageAction.ARCHIVE)

    @staticmethod
    def search(client, search, pager):
        if not search['labels']:  # no access to un-labelled messages
            return []

        return client.get_messages(pager=pager, labels=search['labels'], text=search['text'],
                                   contacts=search['contacts'], groups=search['groups'],
                                   direction='I', _types=['I'], statuses=['H'], archived=search['archived'],
                                   after=search['after'], before=search['before'])

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
                'direction': msg.direction}


class MessageAction(models.Model):
    """
    An action performed on a set of messages
    """
    FLAG = 'F'
    UNFLAG = 'N'
    LABEL = 'L'
    ARCHIVE = 'A'

    ACTION_CHOICES = ((FLAG, _("Flag")),
                      (UNFLAG, _("Un-flag")),
                      (LABEL, _("Label")),
                      (ARCHIVE, _("Archive")))

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
                # 'messages': self.messages, TODO fetch and include length ?
                'action': self.action,
                'created_by': {'id': self.created_by.pk, 'name': self.created_by.get_full_name()},
                'created_on': self.created_on,
                'label': self.label.as_json() if self.label else None}
