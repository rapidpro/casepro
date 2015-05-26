from __future__ import absolute_import, unicode_literals

import json
import pytz

from dash.orgs.models import Org
from dash.utils import random_string, chunks, intersection
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
from temba.base import TembaNoSuchObjectError
from casepro.email import send_email
from . import parse_csv, contact_as_json, match_keywords, SYSTEM_LABEL_FLAGGED


class AccessLevel(IntEnum):
    """
    Case access level
    """
    none = 0
    read = 1
    update = 2


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
            size_by_uuid = {g.uuid: g.size for g in temba_groups}
        else:
            size_by_uuid = {}

        return {g: size_by_uuid[g.uuid] if g.uuid in size_by_uuid else 0 for g in groups}

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

        # fetch all messages to be exported
        messages = Message.search(self.org, search, None)

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
        if not user or user.can_administer(org):
            return cls.objects.filter(org=org, is_active=True)

        partner = user.get_partner()
        return partner.get_labels() if partner else cls.objects.none()

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

    contact_uuid = models.CharField(max_length=36, db_index=True)

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
        return cls.get_all(org).filter(contact_uuid=contact_uuid)

    @classmethod
    def get_open_for_contact_on(cls, org, contact_uuid, dt):
        qs = cls.get_for_contact(org, contact_uuid)
        return qs.filter(opened_on__lt=dt).filter(Q(closed_on=None) | Q(closed_on__gt=dt)).first()

    def get_labels(self):
        return self.labels.filter(is_active=True)

    @classmethod
    def get_or_open(cls, org, user, labels, message, summary, assignee, archive_messages=True):
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

            case = cls.objects.create(org=org, assignee=assignee, contact_uuid=message.contact,
                                      summary=summary, message_id=message.id, message_on=message.created_on)
            case.is_new = True
            case.labels.add(*labels)

            CaseAction.create(case, user, CaseAction.OPEN, assignee=assignee)

            # archive messages and any labelled messages from this contact
            if archive_messages:
                client = org.get_temba_client()
                labels = [l.name for l in Label.get_all(org)]
                messages = client.get_messages(contacts=[message.contact], labels=labels,
                                               direction='I', statuses=['H'], _types=['I'], archived=False)
                message_ids = [m.id for m in messages]
                client.archive_messages(messages=message_ids)

        return case

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

    def _fetch_contact(self):
        try:
            return self.org.get_temba_client().get_contact(self.contact_uuid)
        except TembaNoSuchObjectError:
            return None  # always a chance that the contact has been deleted in RapidPro

    @property
    def is_closed(self):
        return self.closed_on is not None

    def as_json(self, fetch_contact=False):
        if fetch_contact:
            contact = self._fetch_contact()
            contact_json = contact_as_json(contact, self.org.get_contact_fields()) if contact else None
        else:
            contact_json = {'uuid': self.contact_uuid}

        return {'id': self.pk,
                'contact': contact_json,
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
        CaseAction.objects.create(case=case, action=action, created_by=user, assignee=assignee, label=label, note=note)

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
    def bulk_unlabel(org, user, message_ids, label):
        client = org.get_temba_client()
        client.unlabel_messages(message_ids, label=label.name)

        MessageAction.create(org, user, message_ids, MessageAction.UNLABEL, label)

    @staticmethod
    def bulk_archive(org, user, message_ids):
        client = org.get_temba_client()
        client.archive_messages(message_ids)

        MessageAction.create(org, user, message_ids, MessageAction.ARCHIVE)

    @staticmethod
    def bulk_restore(org, user, message_ids):
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

        # don't hit the RapidPro API unless labelling task found new messages
        if search['after']:
            last_msg_time = org.get_last_msg_time()
            if not last_msg_time or search['after'] >= last_msg_time:
                return []

        client = org.get_temba_client()
        messages = client.get_messages(pager=pager, text=search['text'], labels=search['labels'],
                                       contacts=search['contacts'], groups=search['groups'],
                                       direction='I', statuses=['H'], archived=search['archived'],
                                       after=search['after'], before=search['before'])

        if messages:
            org.record_msg_time(messages[0].created_on)

        return messages

    @staticmethod
    def process_unsolicited(org, messages):
        """
        Processes unsolicited messages, labelling and creating case events as appropriate
        """
        labels = list(Label.get_all(org))
        label_keywords = {l: l.get_keywords() for l in labels}
        label_matches = {l: [] for l in labels}  # message ids that match each label

        client = org.get_temba_client()
        num_labels = 0
        newest_labelled = None

        for msg in messages:
            open_case = Case.get_open_for_contact_on(org, msg.contact, msg.created_on)

            if open_case:
                open_case.reply_event(msg)
            else:
                # only apply labels if there isn't a currently open case for this contact
                for label in labels:
                    if match_keywords(msg.text, label_keywords[label]):
                        label_matches[label].append(msg)
                        if not newest_labelled:
                            newest_labelled = msg

        # record the newest/last labelled message time for this org
        if newest_labelled:
            org.record_msg_time(newest_labelled.created_on)

        # add labels to matching messages
        for label, matched_msgs in label_matches.iteritems():
            if matched_msgs:
                client.label_messages(messages=[m.id for m in matched_msgs], label=label.name)
                num_labels += len(matched_msgs)

        return num_labels

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

    broadcast_id = models.IntegerField()

    recipient_count = models.PositiveIntegerField()

    created_by = models.ForeignKey(User, related_name="outgoing_messages")

    created_on = models.DateTimeField(db_index=True)

    case = models.ForeignKey(Case, null=True, related_name="outgoing_messages")

    @classmethod
    def create(cls, org, user, activity, text, urns, contacts, case=None):
        broadcast = org.get_temba_client().create_broadcast(text=text, urns=urns, contacts=contacts)

        # TODO update RapidPro api to expose more accurate recipient_count
        recipient_count = len(broadcast.urns) + len(broadcast.contacts)

        return cls.objects.create(org=org,
                                  broadcast_id=broadcast.id,
                                  recipient_count=recipient_count,
                                  activity=activity, case=case,
                                  created_by=user,
                                  created_on=broadcast.created_on)
