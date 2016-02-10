from __future__ import absolute_import, unicode_literals

import json
import pytz
import re

from casepro.contacts.models import Group
from casepro.msgs.models import Outgoing
from dash.orgs.models import Org
from dash.utils import random_string, chunks, intersection
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from enum import IntEnum
from redis_cache import get_redis_connection
from temba_client.exceptions import TembaNoSuchObjectError, TembaException
from temba_client.utils import parse_iso8601
from casepro.email import send_email
from . import parse_csv, normalize, match_keywords, safe_max, SYSTEM_LABEL_FLAGGED
from .utils import JSONEncoder


# only show unlabelled messages newer than 2 weeks
DEFAULT_UNLABELLED_LIMIT_DAYS = 14


class AccessLevel(IntEnum):
    """
    Case access level
    """
    none = 0
    read = 1
    update = 2


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
        download_url = settings.SITE_HOST_PATTERN % self.org.subdomain + reverse('cases.messageexport_read', args=[self.pk])

        send_email(self.created_by.username, subject, 'cases/email/message_export', dict(link=download_url))

        # force a gc
        import gc
        gc.collect()


class Partner(models.Model):
    """
    Corresponds to a partner organization
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='partners')

    name = models.CharField(verbose_name=_("Name"), max_length=128,
                            help_text=_("Name of this partner organization"))

    logo = models.ImageField(verbose_name=_("Logo"), upload_to='partner_logos', null=True, blank=True)

    is_active = models.BooleanField(default=True, help_text="Whether this partner is active")

    @classmethod
    def create(cls, org, name, logo):
        return cls.objects.create(org=org, name=name, logo=logo)

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

    def release(self):
        # detach all users
        self.user_profiles.update(partner=None)

        self.is_active = False
        self.save(update_fields=('is_active',))

    def as_json(self):
        return {'id': self.pk, 'name': self.name}

    def __unicode__(self):
        return self.name


class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    KEYWORD_MIN_LENGTH = 3

    uuid = models.CharField(max_length=36, unique=True)

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='labels')

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    description = models.CharField(verbose_name=_("Description"), max_length=255)

    keywords = models.CharField(verbose_name=_("Keywords"), max_length=1024, blank=True)

    partners = models.ManyToManyField(Partner, related_name='labels',
                                      help_text=_("Partner organizations who can access messages with this label"))

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
        return len(keyword) >= cls.KEYWORD_MIN_LENGTH and re.match(r'^\w[\w\- ]*\w$', keyword)

    def __unicode__(self):
        return self.name


class Contact(models.Model):
    """
    Maintains some state for a contact whilst they are in a case
    """
    uuid = models.CharField(max_length=36, unique=True)

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='contacts')

    suspended_groups = ArrayField(models.CharField(max_length=36), help_text=_("UUIDs of suspended contact groups"))

    @classmethod
    def get_or_create(cls, org, uuid):
        existing = cls.objects.filter(org=org, uuid=uuid).first()
        if existing:
            return existing

        return cls.objects.create(org=org, uuid=uuid, suspended_groups=[])

    def prepare_for_case(self):
        """
        Prepares this contact to be put in a case
        """
        # suspend contact from groups while case is open
        self.suspend_groups()

        # expire any active flow runs they have
        self.expire_flows()

        # labelling task may have picked up messages whilst case was closed. Those now need to be archived.
        self.archive_messages()

    def suspend_groups(self):
        if self.suspended_groups:
            raise ValueError("Can't suspend from groups as contact is already suspended from groups")

        # get current groups from RapidPro
        temba_contact = self.fetch()
        temba_groups = temba_contact.groups if temba_contact else []

        suspend_groups = [g.uuid for g in Group.get_suspend_from(self.org)]
        remove_groups = intersection(temba_groups, suspend_groups)

        # remove contact from groups
        client = self.org.get_temba_client()
        for remove_group in remove_groups:
            client.remove_contacts([self.uuid], group_uuid=remove_group)

        self.suspended_groups = remove_groups
        self.save(update_fields=('suspended_groups',))

    def restore_groups(self):
        # add contact back into suspended groups
        client = self.org.get_temba_client()
        for suspended_group in self.suspended_groups:
            client.add_contacts([self.uuid], group_uuid=suspended_group)

        self.suspended_groups = []
        self.save(update_fields=('suspended_groups',))

    def expire_flows(self):
        client = self.org.get_temba_client()
        client.expire_contacts([self.uuid])

    def archive_messages(self):
        client = self.org.get_temba_client()
        labels = [l.name for l in Label.get_all(self.org)]
        messages = client.get_messages(contacts=[self.uuid], labels=labels,
                                       direction='I', statuses=['H'], _types=['I'], archived=False)
        if messages:
            client.archive_messages(messages=[m.id for m in messages])

    def fetch(self):
        """
        Fetches this contact from RapidPro
        """
        try:
            return self.org.get_temba_client().get_contact(self.uuid)
        except TembaNoSuchObjectError:
            return None  # always a chance that the contact has been deleted in RapidPro

    def as_json(self, fetch_fields=False):
        """
        Prepares a contact for JSON serialization
        """
        if fetch_fields:
            temba_contact = self.fetch()
            temba_fields = temba_contact.fields if temba_contact else {}

            allowed_keys = self.org.get_contact_fields()
            fields = {key: temba_fields.get(key, None) for key in allowed_keys}
        else:
            fields = {}

        return {'uuid': self.uuid, 'fields': fields}


class case_action(object):
    """
    Helper decorator for case action methods that should check the user is allowed to update the case
    """
    def __init__(self, require_update=True):
        self.require_update = require_update

    def __call__(self, func):
        def wrapped(case, user, *args, **kwargs):
            access = case.access_level(user)
            if (access == AccessLevel.update) or (not self.require_update and access == AccessLevel.read):
                func(case, user, *args, **kwargs)
            else:
                raise PermissionDenied()
        return wrapped


class Case(models.Model):
    """
    A case between a partner organization and a contact
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='cases')

    labels = models.ManyToManyField(Label, verbose_name=_("Labels"), related_name='cases')

    assignee = models.ForeignKey(Partner, related_name="cases")

    contact = models.ForeignKey(Contact, related_name="cases")

    message_id = models.IntegerField(unique=True)

    message_on = models.DateTimeField(help_text="When initial message was sent")

    summary = models.CharField(verbose_name=_("Summary"), max_length=255)

    opened_on = models.DateTimeField(db_index=True, auto_now_add=True,
                                     help_text="When this case was opened")

    closed_on = models.DateTimeField(null=True,
                                     help_text="When this case was closed")

    @classmethod
    def get_all(cls, org, user=None, label=None):
        qs = cls.objects.filter(org=org)

        # if user is not an org admin, we should only return cases with partner labels or assignment
        if user and not user.can_administer(org):
            partner = user.get_partner()
            if partner:
                qs = qs.filter(Q(labels__in=partner.get_labels()) | Q(assignee=partner))
            else:
                return cls.objects.none()

        if label:
            qs = qs.filter(labels=label)

        return qs.distinct()

    @classmethod
    def get_open(cls, org, user=None, label=None):
        return cls.get_all(org, user, label).filter(closed_on=None)

    @classmethod
    def get_closed(cls, org, user=None, label=None):
        return cls.get_all(org, user, label).exclude(closed_on=None)

    @classmethod
    def get_for_contact(cls, org, contact_uuid):
        return cls.get_all(org).filter(contact__uuid=contact_uuid)

    @classmethod
    def get_open_for_contact_on(cls, org, contact_uuid, dt):
        qs = cls.get_for_contact(org, contact_uuid)
        return qs.filter(opened_on__lt=dt).filter(Q(closed_on=None) | Q(closed_on__gt=dt)).first()

    def get_labels(self):
        return self.labels.filter(is_active=True)

    @classmethod
    def get_or_open(cls, org, user, labels, message, summary, assignee, update_contact=True):
        r = get_redis_connection()
        with r.lock('org:%d:cases_lock' % org.pk):
            # check for open case with this contact
            existing_open = cls.get_open_for_contact_on(org, message.contact, timezone.now())
            if existing_open:
                existing_open.is_new = False
                return existing_open

            # check for another case (possibly closed) connected to this message
            existing_for_msg = cls.objects.filter(message_id=message.id).first()
            if existing_for_msg:
                existing_for_msg.is_new = False
                return existing_for_msg

            contact = Contact.get_or_create(org, message.contact)

            if update_contact:
                # suspend from groups, expire flows and archive messages
                contact.prepare_for_case()

            case = cls.objects.create(org=org, assignee=assignee, contact=contact,
                                      summary=summary, message_id=message.id, message_on=message.created_on)
            case.is_new = True
            case.labels.add(*labels)

            CaseAction.create(case, user, CaseAction.OPEN, assignee=assignee)

        return case

    def get_timeline(self, after, before):
        label_map = {l.name: l for l in Label.get_all(self.org)}

        # if this isn't a first request for the existing items, we check on our side to see if there will be new
        # items before hitting the RapidPro API
        do_api_fetch = True
        if after != self.message_on:
            last_event = self.events.order_by('-pk').first()
            last_outgoing = self.outgoing_messages.order_by('-pk').first()
            last_event_time = last_event.created_on if last_event else None
            last_outgoing_time = last_outgoing.created_on if last_outgoing else None
            last_message_time = safe_max(last_event_time, last_outgoing_time)
            do_api_fetch = last_message_time and after <= last_message_time

        if do_api_fetch:
            # fetch messages
            remote = self.org.get_temba_client().get_messages(contacts=[self.contact.uuid],
                                                              after=after,
                                                              before=before)

            local_outgoing = self.outgoing_messages.filter(created_on__gte=after, created_on__lte=before)
            local_by_broadcast = {o.broadcast_id: o for o in local_outgoing}

            # merge remotely fetched and local outgoing messages
            messages = []
            for m in remote:
                local = local_by_broadcast.pop(m.broadcast, None)
                if local:
                    m.sender = local.created_by
                messages.append({'time': m.created_on, 'type': 'M', 'item': RemoteMessage.as_json(m, label_map)})

            for m in local_by_broadcast.values():
                messages.append({'time': m.created_on, 'type': 'M', 'item': m.as_json()})

        else:
            messages = []

        # fetch actions in chronological order
        actions = self.actions.filter(created_on__gte=after, created_on__lte=before)
        actions = actions.select_related('assignee', 'created_by').order_by('pk')

        # merge actions and messages and JSON-ify both
        timeline = messages
        timeline += [{'time': a.created_on, 'type': 'A', 'item': a.as_json()} for a in actions]
        timeline = sorted(timeline, key=lambda event: event['time'])
        return timeline

    @case_action()
    def update_summary(self, user, summary):
        self.summary = summary
        self.save(update_fields=('summary',))

        CaseAction.create(self, user, CaseAction.UPDATE_SUMMARY, note=None)

    @case_action(require_update=False)
    def add_note(self, user, note):
        CaseAction.create(self, user, CaseAction.ADD_NOTE, note=note)

    @case_action()
    def close(self, user, note=None):
        self.contact.restore_groups()

        close_action = CaseAction.create(self, user, CaseAction.CLOSE, note=note)

        self.closed_on = close_action.created_on
        self.save(update_fields=('closed_on',))

    @case_action()
    def reopen(self, user, note=None, update_contact=True):
        self.closed_on = None
        self.save(update_fields=('closed_on',))

        CaseAction.create(self, user, CaseAction.REOPEN, note=note)

        if update_contact:
            # suspend from groups, expire flows and archive messages
            self.contact.prepare_for_case()

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

    def reply_event(self, msg):
        CaseEvent.create_reply(self, msg)

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

    def access_level(self, user):
        """
        A user can view a case if one of these conditions is met:
            1) they are an administrator for the case org
            2) their partner org is assigned to the case
            3) their partner org can view a label assigned to the case

        They can additionally update the case if 1) or 2) is true
        """
        if user.can_administer(self.org) or user.profile.partner == self.assignee:
            return AccessLevel.update
        elif user.profile.partner and intersection(self.get_labels(), user.profile.partner.get_labels()):
            return AccessLevel.read
        else:
            return AccessLevel.none

    @property
    def is_closed(self):
        return self.closed_on is not None

    def as_json(self, fetch_contact=False):
        return {'id': self.pk,
                'contact': self.contact.as_json(fetch_contact),
                'assignee': self.assignee.as_json(),
                'labels': [l.as_json() for l in self.get_labels()],
                'summary': self.summary,
                'opened_on': self.opened_on,
                'is_closed': self.is_closed}

    def __unicode__(self):
        return '#%d' % self.pk


class CaseAction(models.Model):
    """
    An action performed on a case
    """
    OPEN = 'O'
    UPDATE_SUMMARY = 'S'
    ADD_NOTE = 'N'
    REASSIGN = 'A'
    LABEL = 'L'
    UNLABEL = 'U'
    CLOSE = 'C'
    REOPEN = 'R'

    ACTION_CHOICES = ((OPEN, _("Open")),
                      (ADD_NOTE, _("Add Note")),
                      (REASSIGN, _("Reassign")),
                      (LABEL, _("Label")),
                      (UNLABEL, _("Remove Label")),
                      (CLOSE, _("Close")),
                      (REOPEN, _("Reopen")))

    case = models.ForeignKey(Case, related_name="actions")

    action = models.CharField(max_length=1, choices=ACTION_CHOICES)

    created_by = models.ForeignKey(User, related_name="case_actions")

    created_on = models.DateTimeField(db_index=True, auto_now_add=True)

    assignee = models.ForeignKey(Partner, null=True, related_name="case_actions")

    label = models.ForeignKey(Label, null=True)

    note = models.CharField(null=True, max_length=1024)

    @classmethod
    def create(cls, case, user, action, assignee=None, label=None, note=None):
        return CaseAction.objects.create(case=case, action=action,
                                         created_by=user, assignee=assignee, label=label, note=note)

    def as_json(self):
        return {'id': self.pk,
                'action': self.action,
                'created_by': {'id': self.created_by.pk, 'name': self.created_by.get_full_name()},
                'created_on': self.created_on,
                'assignee': self.assignee.as_json() if self.assignee else None,
                'label': self.label.as_json() if self.label else None,
                'note': self.note}


class CaseEvent(models.Model):
    """
    An event (i.e. non-user action) relating to a case
    """
    REPLY = 'R'

    EVENT_CHOICES = ((REPLY, _("Contact replied")),)

    case = models.ForeignKey(Case, related_name="events")

    event = models.CharField(max_length=1, choices=EVENT_CHOICES)

    created_on = models.DateTimeField(db_index=True)

    @classmethod
    def create_reply(cls, case, msg):
        cls.objects.create(case=case, event=cls.REPLY, created_on=msg.created_on)

    def as_json(self):
        return {'id': self.pk,
                'event': self.event,
                'created_on': self.created_on}


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

        # try to limit actual hits to the RapidPro API
        if search['after']:
            # don't hit the RapidPro API unless labelling task found new messages
            latest_time = org.get_last_message_time(labelled=labelled_search)
            if not latest_time or search['after'] >= latest_time:
                return []

        # put limit on how far back we fetch unlabelled messages because there are lots of those
        if not labelled_search and not search['after']:
            limit_days = getattr(settings, 'UNLABELLED_LIMIT_DAYS', DEFAULT_UNLABELLED_LIMIT_DAYS)
            search['after'] = timezone.now() - timedelta(days=limit_days)

        # *** TEMPORARY *** fix to disable the Unlabelled view which is increasingly not performant, until the larger
        # message store refactor is complete. This removes any label exclusions from the search.
        search['labels'] = [l for l in search['labels'] if not l.startswith('-')]

        client = org.get_temba_client()
        messages = client.get_messages(pager=pager, text=search['text'], labels=search['labels'],
                                       contacts=search['contacts'], groups=search['groups'],
                                       direction='I', _types=search['types'], archived=search['archived'],
                                       after=search['after'], before=search['before'])

        if messages:
            org.record_message_time(messages[0].created_on, labelled_search)

        return messages

    @staticmethod
    def process_unsolicited(org, messages):
        """
        Processes unsolicited messages, labelling and creating case events as appropriate
        """
        labels = list(Label.get_all(org))
        label_keywords = {l: l.get_keywords() for l in labels}
        label_matches = {l: [] for l in labels}  # message ids that match each label

        case_replies = []

        client = org.get_temba_client()
        labelled, unlabelled = [], []

        for msg in messages:
            open_case = Case.get_open_for_contact_on(org, msg.contact, msg.created_on)

            if open_case:
                open_case.reply_event(msg)
                case_replies.append(msg)
            else:
                # only apply labels if there isn't a currently open case for this contact
                norm_text = normalize(msg.text)

                for label in labels:
                    if match_keywords(norm_text, label_keywords[label]):
                        labelled.append(msg)
                        label_matches[label].append(msg)

        # add labels to matching messages
        for label, matched_msgs in label_matches.iteritems():
            if matched_msgs:
                client.label_messages(messages=matched_msgs, label_uuid=label.uuid)

        # archive messages which are case replies
        if case_replies:
            client.archive_messages(messages=case_replies)

        # record the last labelled/unlabelled message times for this org
        if labelled:
            org.record_message_time(labelled[0].created_on, labelled=True)
        if unlabelled:
            org.record_message_time(unlabelled[0].created_on, labelled=False)

        return len(labelled)

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
                'direction': msg.direction,
                'archived': msg.archived,
                'sender': msg.sender.as_json() if getattr(msg, 'sender', None) else None}


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
