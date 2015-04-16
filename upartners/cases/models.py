from __future__ import absolute_import, unicode_literals

import json
import pytz

from dash.orgs.models import Org
from dash.utils import get_obj_cacheable, random_string
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from upartners.email import send_upartners_email
from . import parse_csv, SYSTEM_LABEL_FLAGGED
from .tasks import update_labelling_flow


ACTION_OPEN = 'O'
ACTION_NOTE = 'N'
ACTION_REASSIGN = 'A'
ACTION_CLOSE = 'C'
ACTION_REOPEN = 'R'

CASE_ACTION_CHOICES = ((ACTION_OPEN, _("Open")),
                       (ACTION_NOTE, _("Add Note")),
                       (ACTION_REASSIGN, _("Reassign")),
                       (ACTION_CLOSE, _("Close")),
                       (ACTION_REOPEN, _("Reopen")))


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
        download_url = 'https://%s%s' % (settings.HOSTNAME, reverse('cases.messageexport_read', args=[self.pk]))

        # force a gc
        import gc
        gc.collect()

        send_upartners_email(self.created_by.username, subject, 'cases/email/message_export', dict(link=download_url))


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

    uuid = models.CharField(max_length=36, null=True)

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    description = models.CharField(verbose_name=_("Description"), max_length=255)

    keywords = models.CharField(verbose_name=_("Keywords"), max_length=1024, blank=True)

    partners = models.ManyToManyField(Partner, related_name='labels',
                                      help_text=_("Partner organizations who can access messages with this label"))

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    @classmethod
    def create(cls, org, name, description, keywords, partners, uuid=None, update_flow=True):
        label = cls.objects.create(org=org, name=name, description=description, keywords=','.join(keywords), uuid=uuid)
        label.partners.add(*partners)

        if update_flow:
            update_labelling_flow.delay(label.org_id)

        return label

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org, is_active=True)

    @classmethod
    def fetch_counts(cls, org, labels):
        label_by_uuid = {l.uuid: l for l in labels if l.uuid}
        if label_by_uuid:
            temba_labels = org.get_temba_client().get_labels(uuids=label_by_uuid.keys())
            counts_by_uuid = {l.uuid: l.count for l in temba_labels}
        else:
            counts_by_uuid = {}

        return {l: counts_by_uuid[l.uuid] if l.uuid in counts_by_uuid else 0 for l in labels}

    def get_count(self):
        return get_obj_cacheable(self, '_count', lambda: self.fetch_counts(self.org, [self])[self])

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

    opened_on = models.DateTimeField(auto_now_add=True,
                                     help_text="When this case was opened")

    closed_on = models.DateTimeField(null=True,
                                     help_text="When this case was closed")

    @classmethod
    def get_all(cls, org, label=None):
        qs = cls.objects.filter(org=org)
        if label:
            qs = qs.filter(labels=label)
        return qs

    @classmethod
    def get_open(cls, org, label=None):
        return cls.get_all(org, label).filter(closed_on=None)

    @classmethod
    def get_closed(cls, org, label=None):
        return cls.get_all(org, label).exclude(closed_on=None)

    @classmethod
    def get_for_contact(cls, org, contact_uuid):
        return cls.get_all(org).filter(contact_uuid)

    def get_labels(self):
        return self.labels.filter(is_active=True)

    @classmethod
    def open(cls, org, user, labels, partner, contact_uuid, message_id, message_on):
        case = cls.objects.create(org=org, assignee=partner, contact_uuid=contact_uuid,
                                  message_id=message_id, message_on=message_on)

        case.labels.add(*labels)

        CaseAction.create(case, user, ACTION_OPEN, assignee=partner)
        return case

    def note(self, user, note):
        CaseAction.create(self, user, ACTION_NOTE, note=note)

    def close(self, user, note=None):
        if not self._can_edit(user):
            raise PermissionDenied()

        self.closed_on = timezone.now()
        self.save(update_fields=('closed_on',))

        CaseAction.create(self, user, ACTION_CLOSE, note=note)

    def reopen(self, user, note=None):
        if not self._can_edit(user):
            raise PermissionDenied()

        self.closed_on = None
        self.save(update_fields=('closed_on',))

        CaseAction.create(self, user, ACTION_REOPEN, note=note)

    def reassign(self, user, partner, note=None):
        if not self._can_edit(user):
            raise PermissionDenied()

        self.assignee = partner
        self.save(update_fields=('assignee',))

        CaseAction.create(self, user, ACTION_REASSIGN, assignee=partner, note=note)

    def _can_edit(self, user):
        if user.is_admin_for(self.org):
            return True

        return user.has_profile() and user.profile.partner == self.assignee

    def as_json(self):
        return {'id': self.pk,
                'assignee': self.assignee.as_json(),
                'labels': [l.as_json() for l in self.get_labels()],
                'is_closed': self.closed_on is not None}


class CaseAction(models.Model):
    """
    An action performed on a case
    """
    case = models.ForeignKey(Case, related_name="actions")

    action = models.CharField(max_length=1, choices=CASE_ACTION_CHOICES)

    created_by = models.ForeignKey(User, related_name="case_actions")

    created_on = models.DateTimeField(auto_now_add=True)

    assignee = models.ForeignKey(Partner, null=True, related_name="case_actions")

    note = models.CharField(null=True, max_length=1024)

    @classmethod
    def create(cls, case, user, action, assignee=None, note=None):
        CaseAction.objects.create(case=case, action=action, created_by=user, assignee=assignee, note=note)

    def as_json(self):
        return {'id': self.pk,
                'action': self.action,
                'created_by': {'id': self.created_by.pk, 'name': self.created_by.get_full_name()},
                'created_on': self.created_on,
                'assignee': self.assignee.as_json() if self.assignee else None,
                'note': self.note}

    class Meta:
        ordering = ('pk',)
