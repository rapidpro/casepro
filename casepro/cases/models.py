from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from dash.utils import intersection
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q, Count, Prefetch
from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from enum import Enum, IntEnum
from itertools import chain
from django_redis import get_redis_connection

from casepro.backend import get_backend
from casepro.contacts.models import Contact
from casepro.msgs.models import Label, Message, Outgoing
from casepro.utils import TimelineItem
from casepro.utils.export import BaseSearchExport


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

    is_restricted = models.BooleanField(default=True, verbose_name=_("Restricted Access"),
                                        help_text=_("Whether this partner's access is restricted by labels"))

    labels = models.ManyToManyField(Label, verbose_name=_("Labels"), related_name='partners',
                                    help_text=_("Labels that this partner can access"))

    logo = models.ImageField(verbose_name=_("Logo"), upload_to='partner_logos', null=True, blank=True)

    is_active = models.BooleanField(default=True, help_text="Whether this partner is active")

    @classmethod
    def create(cls, org, name, restricted, labels, logo=None):
        if labels and not restricted:
            raise ValueError("Can't specify labels for a partner which is not restricted")

        partner = cls.objects.create(org=org, name=name, logo=logo, is_restricted=restricted)

        if restricted:
            partner.labels.add(*labels)

        return partner

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org, is_active=True)

    def get_labels(self):
        return self.labels.filter(is_active=True) if self.is_restricted else Label.get_all(self.org)

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

    def as_json(self, full=True):
        result = {'id': self.pk, 'name': self.name}

        if full:
            result['restricted'] = self.is_restricted

        return result

    def __str__(self):
        return self.name


class case_action(object):
    """
    Helper decorator for case action methods that should check the user is allowed to update the case
    """
    def __init__(self, require_update=True, become_watcher=False):
        self.require_update = require_update
        self.become_watcher = become_watcher

    def __call__(self, func):
        def wrapped(case, user, *args, **kwargs):
            access = case.access_level(user)
            if (access == AccessLevel.update) or (not self.require_update and access == AccessLevel.read):
                result = func(case, user, *args, **kwargs)

                if self.become_watcher:
                    case.watchers.add(user)

                return result
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

    user_assignee = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='cases',
        help_text="The (optional) user that this case is assigned to")

    contact = models.ForeignKey(Contact, related_name='cases')

    initial_message = models.OneToOneField(Message, related_name='initial_case')

    summary = models.CharField(verbose_name=_("Summary"), max_length=255)

    opened_on = models.DateTimeField(auto_now_add=True,
                                     help_text="When this case was opened")

    closed_on = models.DateTimeField(null=True,
                                     help_text="When this case was closed")

    last_reassigned_on = models.DateTimeField(null=True,
                                              help_text="When this case was last reassigned")

    last_assignee = models.ForeignKey(Partner, null=True, related_name='previously_assigned_cases')

    last_user_assignee = models.ForeignKey(User, null=True,
                                           on_delete=models.SET_NULL, related_name='previously_assigned_cases')

    watchers = models.ManyToManyField(User, related_name='watched_cases',
                                      help_text="Users to be notified of case activity")

    @classmethod
    def get_all(cls, org, user=None, label=None):
        queryset = cls.objects.filter(org=org)

        if user:
            # if user is not an org admin, we should only return cases with partner labels or assignment
            user_partner = user.get_partner(org)
            if user_partner and user_partner.is_restricted:
                queryset = queryset.filter(Q(labels__in=list(user_partner.get_labels())) | Q(assignee=user_partner))

        if label:
            queryset = queryset.filter(labels=label)

        return queryset.distinct()

    @classmethod
    def get_all_passed_response_time(cls, check_datetime=None):
        response_required_in = getattr(settings, 'SITE_CASE_RESPONSE_REQUIRED_TIME', None)
        if response_required_in is None:
            # if the response timeout is not configured, return an empty queryset to maintain backwards compatibility
            return cls.objects.none()

        if check_datetime is None:
            check_datetime = now()

        expired_on = check_datetime - timedelta(minutes=response_required_in)
        queryset = cls.objects.filter(closed_on=None, last_reassigned_on__lt=expired_on)
        return queryset

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
        folder = search.get('folder')
        assignee_id = search.get('assignee')
        after = search.get('after')
        before = search.get('before')

        if folder == CaseFolder.open:
            queryset = Case.get_open(org, user)
        elif folder == CaseFolder.closed:
            queryset = Case.get_closed(org, user)
        else:  # pragma: no cover
            raise ValueError('Invalid folder for cases')

        if assignee_id:
            queryset = queryset.filter(assignee__pk=assignee_id)

        if after:
            queryset = queryset.filter(opened_on__gte=after)
        if before:
            queryset = queryset.filter(opened_on__lte=before)

        queryset = queryset.select_related('contact', 'assignee')

        queryset = queryset.prefetch_related(
            Prefetch('labels', Label.objects.filter(is_active=True))
        )

        return queryset.order_by('-opened_on')

    @classmethod
    def get_or_open(cls, org, user, message, summary, assignee):
        from casepro.profiles.models import Notification

        r = get_redis_connection()
        with r.lock(CASE_LOCK_KEY % (org.pk, message.contact.uuid)):
            message.refresh_from_db()

            # if message is already associated with a case, return that
            if message.case:
                message.case.is_new = False
                return message.case

            # suspend from groups, expire flows and archive messages
            message.contact.prepare_for_case()

            case = cls.objects.create(org=org, assignee=assignee, initial_message=message, contact=message.contact,
                                      summary=summary)
            case.is_new = True
            case.labels.add(*list(message.labels.all()))  # copy labels from message to new case
            case.watchers.add(user)

            # attach message to this case
            message.case = case
            message.save(update_fields=('case',))

            action = CaseAction.create(case, user, CaseAction.OPEN, assignee=assignee)

            for assignee_user in assignee.get_users():
                if assignee_user != user:
                    Notification.new_case_assignment(org, assignee_user, action)

        return case

    def get_timeline(self, after, before, merge_from_backend):
        local_outgoing = self.outgoing_messages.filter(created_on__gte=after, created_on__lte=before)
        local_outgoing = local_outgoing.select_related('case', 'contact', 'created_by').order_by('-created_on')

        local_incoming = self.incoming_messages.filter(created_on__gte=after, created_on__lte=before)
        local_incoming = local_incoming.select_related('case', 'contact').prefetch_related('labels')
        local_incoming = local_incoming.order_by('-created_on')

        # merge local incoming and outgoing
        timeline = [TimelineItem(msg) for msg in chain(local_outgoing, local_incoming)]

        if merge_from_backend:
            # if this is the initial request, fetch additional messages from the backend
            backend = get_backend()
            backend_messages = backend.fetch_contact_messages(self.org, self.contact, after, before)

            # add any backend messages that don't exist locally
            if backend_messages:
                local_broadcast_ids = {o.backend_broadcast_id for o in local_outgoing if o.backend_broadcast_id}

                for msg in backend_messages:
                    if msg.backend_broadcast_id not in local_broadcast_ids:
                        timeline.append(TimelineItem(msg))

        # fetch and append actions
        actions = self.actions.filter(created_on__gte=after, created_on__lte=before)
        actions = actions.select_related('assignee', 'created_by')
        timeline += [TimelineItem(a) for a in actions]

        # sort timeline by reverse chronological order
        return sorted(timeline, key=lambda item: item.get_time())

    def add_reply(self, message):
        message.case = self
        message.is_archived = True
        message.save(update_fields=('case', 'is_archived'))

        self.notify_watchers(reply=message)

    @case_action()
    def update_summary(self, user, summary):
        self.summary = summary
        self.save(update_fields=('summary',))

        CaseAction.create(self, user, CaseAction.UPDATE_SUMMARY, note=None)

    @case_action(require_update=False, become_watcher=True)
    def add_note(self, user, note):
        action = CaseAction.create(self, user, CaseAction.ADD_NOTE, note=note)

        self.notify_watchers(action=action)

    @case_action()
    def close(self, user, note=None):
        self.contact.restore_groups()

        action = CaseAction.create(self, user, CaseAction.CLOSE, note=note)

        self.closed_on = action.created_on
        self.save(update_fields=('closed_on',))

        self.notify_watchers(action=action)

    @case_action(become_watcher=True)
    def reopen(self, user, note=None, update_contact=True):
        self.closed_on = None
        self.save(update_fields=('closed_on',))

        action = CaseAction.create(self, user, CaseAction.REOPEN, note=note)

        if update_contact:
            # suspend from groups, expire flows and archive messages
            self.contact.prepare_for_case()

        self.notify_watchers(action=action)

    @case_action()
    def reassign(self, user, partner, note=None, user_assignee=None):
        from casepro.profiles.models import Notification

        self.last_reassigned_on = now()
        self.last_assignee = self.assignee
        self.last_user_assignee = self.user_assignee
        self.assignee = partner
        self.user_assignee = user_assignee
        self.save()

        action = CaseAction.create(self, user, CaseAction.REASSIGN, assignee=partner, note=note)

        self.notify_watchers(action=action)

        # also notify users in the assigned partner that this case has been assigned to them
        for user in partner.get_users():
            Notification.new_case_assignment(self.org, user, action)

    @case_action()
    def label(self, user, label):
        self.labels.add(label)

        CaseAction.create(self, user, CaseAction.LABEL, label=label)

    @case_action()
    def unlabel(self, user, label):
        self.labels.remove(label)

        CaseAction.create(self, user, CaseAction.UNLABEL, label=label)

    @case_action(become_watcher=True)
    def reply(self, user, text):
        return Outgoing.create_case_reply(self.org, user, text, self)

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

    def watch(self, user):
        if self.access_level(user) != AccessLevel.none:
            self.watchers.add(user)
        else:
            raise PermissionDenied()

    def unwatch(self, user):
        self.watchers.remove(user)

    def is_watched_by(self, user):
        return user in self.watchers.all()

    def notify_watchers(self, reply=None, action=None):
        from casepro.profiles.models import Notification

        for watcher in self.watchers.all():
            if reply:
                Notification.new_case_reply(self.org, watcher, reply)
            elif action and watcher != action.created_by:
                Notification.new_case_action(self.org, watcher, action)

    def access_level(self, user):
        """
        A user can view a case if one of these conditions is met:
            1) they're a superuser
            2) they're a non-partner user from same org
            3) they're a partner user in partner which is not restricted
            4) their partner org is assigned to the case
            5) their partner org can view a label assigned to the case

        They can additionally update the case if one of 1-4 is true
        """
        if not user.is_superuser and not self.org.get_user_org_group(user):
            return AccessLevel.none

        user_partner = user.get_partner(self.org)

        if user.is_superuser or not user_partner or not user_partner.is_restricted or user_partner == self.assignee:
            return AccessLevel.update
        elif user_partner and intersection(self.labels.filter(is_active=True), user_partner.get_labels()):
            return AccessLevel.read
        else:
            return AccessLevel.none

    @property
    def is_closed(self):
        return self.closed_on is not None

    def as_json(self, full=True):
        if full:
            return {
                'id': self.pk,
                'assignee': self.assignee.as_json(full=False),
                'contact': self.contact.as_json(full=False),
                'labels': [l.as_json(full=False) for l in self.labels.all()],
                'summary': self.summary,
                'opened_on': self.opened_on,
                'is_closed': self.is_closed
            }
        else:
            return {
                'id': self.pk,
                'assignee': self.assignee.as_json(full=False),
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

    TIMELINE_TYPE = 'A'

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
            'created_by': self.created_by.as_json(full=False),
            'created_on': self.created_on,
            'assignee': self.assignee.as_json() if self.assignee else None,
            'label': self.label.as_json() if self.label else None,
            'note': self.note
        }


class CaseExport(BaseSearchExport):
    """
    An export of cases
    """
    directory = 'case_exports'
    download_view = 'cases.caseexport_read'

    def get_search(self):
        search = super(CaseExport, self).get_search()
        search['folder'] = CaseFolder[search['folder']]
        return search

    def render_search(self, book, search):
        from casepro.contacts.models import Field

        base_fields = [
            "Message On", "Opened On", "Closed On", "Assigned Partner", "Labels", "Summary",
            "Messages Sent", "Messages Received", "Contact"
        ]
        contact_fields = Field.get_all(self.org, visible=True)
        all_fields = base_fields + [f.label for f in contact_fields]

        # load all messages to be exported
        items = Case.search(self.org, self.created_by, search)

        items = items.select_related('initial_message')  # need for "Message On"

        items = items.annotate(
            incoming_count=Count('incoming_messages', distinct=True),
            outgoing_count=Count('outgoing_messages', distinct=True)
        )

        def add_sheet(num):
            sheet = book.add_sheet(unicode(_("Cases %d" % num)))
            self.write_row(sheet, 0, all_fields)
            return sheet

        sheet = None
        sheet_number = 0
        row = 1
        for item in items:
            if not sheet or row > self.MAX_SHEET_ROWS:
                sheet_number += 1
                sheet = add_sheet(sheet_number)
                row = 1

            values = [
                item.initial_message.created_on,
                item.opened_on,
                item.closed_on,
                item.assignee.name,
                ', '.join([l.name for l in item.labels.all()]),
                item.summary,
                item.outgoing_count,
                item.incoming_count - 1,  # subtract 1 for the initial messages
                item.contact.uuid
            ]

            fields = item.contact.get_fields()
            for field in contact_fields:
                values.append(fields.get(field.key, ""))

            self.write_row(sheet, row, values)
            row += 1
