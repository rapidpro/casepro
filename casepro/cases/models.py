from __future__ import absolute_import, unicode_literals

import pytz

from casepro.backend import get_backend
from casepro.contacts.models import Contact
from casepro.msgs.models import Label, Message
from casepro.utils.export import BaseExport
from dash.orgs.models import Org
from dash.utils import intersection, chunks
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from enum import Enum, IntEnum
from redis_cache import get_redis_connection


CASE_LOCK_KEY = 'org:%d:case_lock:%s'


class CaseFolder(Enum):
    open = 1
    closed = 2


class AccessLevel(IntEnum):
    """
    Case access level
    """
    none = 0
    read = 1
    update = 2


@python_2_unicode_compatible
class Partner(models.Model):
    """
    Corresponds to a partner organization
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='partners')

    name = models.CharField(verbose_name=_("Name"), max_length=128,
                            help_text=_("Name of this partner organization"))

    labels = models.ManyToManyField(Label, verbose_name=_("Labels"), related_name='partners',
                                    help_text=_("Labels that this partner can access"))

    logo = models.ImageField(verbose_name=_("Logo"), upload_to='partner_logos', null=True, blank=True)

    is_active = models.BooleanField(default=True, help_text="Whether this partner is active")

    @classmethod
    def create(cls, org, name, labels, logo):
        partner = cls.objects.create(org=org, name=name, logo=logo)

        for label in labels:
            partner.labels.add(label)

        return partner

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

    def __str__(self):
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


@python_2_unicode_compatible
class Case(models.Model):
    """
    A case between a partner organization and a contact
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='cases')

    labels = models.ManyToManyField(Label, help_text=_("Labels assigned to this case"))

    assignee = models.ForeignKey(Partner, related_name='cases')

    contact = models.ForeignKey(Contact, related_name='cases')

    initial_message = models.OneToOneField(Message, related_name='initial_case')

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
    def get_for_contact(cls, org, contact):
        return cls.get_all(org).filter(contact=contact)

    @classmethod
    def get_open_for_contact_on(cls, org, contact, dt):
        qs = cls.get_for_contact(org, contact)
        return qs.filter(opened_on__lt=dt).filter(Q(closed_on=None) | Q(closed_on__gt=dt)).first()

    @classmethod
    def search(cls, org, user, search):
        """
        Search for cases
        """
        if search['folder'] == CaseFolder.open:
            queryset = Case.get_open(org, user)
        elif search['folder'] == CaseFolder.closed:
            queryset = Case.get_closed(org, user)
        else:
            raise ValueError('Invalid folder for cases')

        if search['assignee']:
            queryset = queryset.filter(assignee__pk=search['assignee'])

        if search['after']:
            queryset = queryset.filter(opened_on__gt=search['after'])
        if search['before']:
            queryset = queryset.filter(opened_on__lt=search['before'])

        queryset = queryset.prefetch_related('labels').select_related('contact', 'assignee')

        return queryset.order_by('-pk')

    def get_labels(self):
        return self.labels.filter(is_active=True)

    @classmethod
    def get_or_open(cls, org, user, message, summary, assignee):
        r = get_redis_connection()
        with r.lock(CASE_LOCK_KEY % (org.pk, message.contact.uuid)):
            # if message is already associated with a case, return that
            if message.case:
                message.case.is_new = False
                return message.case

            # if message contact has an open case, return that
            existing_open = cls.get_open_for_contact_on(org, message.contact, timezone.now())
            if existing_open:
                existing_open.is_new = False
                return existing_open

            # suspend from groups, expire flows and archive messages
            message.contact.prepare_for_case()

            case = cls.objects.create(org=org, assignee=assignee, initial_message=message, contact=message.contact,
                                      summary=summary)
            case.is_new = True
            case.labels.add(*list(message.labels.all()))  # copy labels from message to new case

            # attach message to this case
            message.case = case
            message.save(update_fields=('case',))

            CaseAction.create(case, user, CaseAction.OPEN, assignee=assignee)

        return case

    def get_timeline(self, after, before, merge_from_backend):
        messages = []

        local_outgoing = self.outgoing_messages.filter(created_on__gte=after, created_on__lte=before)
        local_outgoing = local_outgoing.select_related('case__contact')

        if merge_from_backend:
            # if this is the initial request, get a more complete timeline from the backend
            backend = get_backend()
            backend_messages = backend.fetch_contact_messages(self.org, self.contact, after, before)

            local_by_broadcast = {o.broadcast_id: o for o in local_outgoing}

            for msg in backend_messages:
                # annotate with sender from local message if there is one
                local = local_by_broadcast.pop(msg['broadcast'], None)
                msg['sender'] = local.created_by.as_json() if local else None

                messages.append({'time': msg['time'], 'type': 'M', 'item': msg})

            for msg in local_by_broadcast.values():
                messages.append({'time': msg.created_on, 'type': 'M', 'item': msg.as_json()})
        else:
            # otherwise just merge local outgoing and incoming messages
            for msg in local_outgoing:
                messages.append({'time': msg.created_on, 'type': 'M', 'item': msg.as_json()})

            local_incoming = self.incoming_messages.filter(created_on__gte=after, created_on__lte=before)
            local_incoming = local_incoming.select_related('contact')

            for msg in local_incoming:
                messages.append({'time': msg.created_on, 'type': 'M', 'item': msg.as_json()})

        # fetch actions in chronological order
        actions = self.actions.filter(created_on__gte=after, created_on__lte=before)
        actions = actions.select_related('assignee', 'created_by').order_by('pk')
        actions = [{'time': a.created_on, 'type': 'A', 'item': a.as_json()} for a in actions]

        # merge actions and messages and sort by time
        return sorted(messages + actions, key=lambda event: event['time'])

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

    def as_json(self, full_contact=False):
        return {
            'id': self.pk,
            'contact': self.contact.as_json(full_contact),
            'assignee': self.assignee.as_json(),
            'labels': [l.as_json() for l in self.get_labels()],
            'summary': self.summary,
            'opened_on': self.opened_on,
            'is_closed': self.is_closed
        }

    def __str__(self):
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
        return {
            'id': self.pk,
            'action': self.action,
            'created_by': {'id': self.created_by.pk, 'name': self.created_by.get_full_name()},
            'created_on': self.created_on,
            'assignee': self.assignee.as_json() if self.assignee else None,
            'label': self.label.as_json() if self.label else None,
            'note': self.note
        }


class CaseExport(BaseExport):
    """
    An export of cases
    """
    directory = 'case_exports'
    download_view = 'cases.caseexport_read'
    email_templates = 'cases/email/case_export'

    def get_search(self):
        search = super(CaseExport, self).get_search()
        search['folder'] = CaseFolder[search['folder']]
        return search

    def render_book(self, book, search):
        from casepro.contacts.models import Field

        base_fields = ["Opened On", "Closed On", "Labels", "Summary", "Contact"]
        contact_fields = Field.get_all(self.org, visible=True)
        all_fields = base_fields + [f.label for f in contact_fields]

        # load all messages to be exported
        cases = Case.search(self.org, self.created_by, search)

        def add_sheet(num):
            sheet = book.add_sheet(unicode(_("Cases %d" % num)))
            for col in range(len(all_fields)):
                field = all_fields[col]
                sheet.write(0, col, unicode(field))
            return sheet

        # even if there are no cases - still add a sheet
        if not cases:
            add_sheet(1)
        else:
            sheet_number = 1
            for case_chunk in chunks(cases, 65535):
                current_sheet = add_sheet(sheet_number)

                row = 1
                for case in case_chunk:
                    opened_on = case.opened_on.astimezone(pytz.UTC).replace(tzinfo=None)
                    closed_on = case.closed_on.astimezone(pytz.UTC).replace(tzinfo=None) if case.closed_on else None

                    current_sheet.write(row, 0, opened_on, self.DATE_STYLE)
                    current_sheet.write(row, 1, closed_on, self.DATE_STYLE)
                    current_sheet.write(row, 2, ', '.join([l.name for l in case.labels.all()]))
                    current_sheet.write(row, 3, case.summary)
                    current_sheet.write(row, 4, case.contact.uuid)

                    fields = case.contact.get_fields()

                    for cf in range(len(contact_fields)):
                        contact_field = contact_fields[cf]
                        current_sheet.write(row, len(base_fields) + cf, fields.get(contact_field.key, None))

                    row += 1

                sheet_number += 1

        return book
