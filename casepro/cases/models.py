from __future__ import absolute_import, unicode_literals

import re
import six

from casepro.contacts.models import Contact
from casepro.msgs.models import RemoteMessage
from casepro.utils import parse_csv
from dash.orgs.models import Org
from dash.utils import intersection
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from enum import IntEnum
from redis_cache import get_redis_connection
from temba_client.exceptions import TembaException


class AccessLevel(IntEnum):
    """
    Case access level
    """
    none = 0
    read = 1
    update = 2


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
        return len(keyword) >= cls.KEYWORD_MIN_LENGTH and re.match(r'^\w[\w\- ]*\w$', keyword)

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

    contact = models.ForeignKey(Contact, related_name="cases", null=True)

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
    def get_for_contact(cls, org, contact):
        return cls.get_all(org).filter(contact=contact)

    @classmethod
    def get_open_for_contact_on(cls, org, contact, dt):
        qs = cls.get_for_contact(org, contact)
        return qs.filter(opened_on__lt=dt).filter(Q(closed_on=None) | Q(closed_on__gt=dt)).first()

    def get_labels(self):
        return self.labels.filter(is_active=True)

    @classmethod
    def get_or_open(cls, org, user, labels, message, summary, assignee, update_contact=True):
        # TODO: until contacts are all pulled in locally, we need to create/update them as cases are opened
        contact_uuid = message.contact.uuid

        with Contact.sync_lock(contact_uuid):
            contact = Contact.objects.filter(org=org, uuid=contact_uuid).first()
            temba_contact = org.get_temba_client(api_version=2).get_contacts(uuid=contact_uuid).first()

            if not temba_contact:
                raise ValueError("Can't create case for contact which has been deleted")

            local_kwargs = Contact.sync_get_kwargs(org, temba_contact)

            if contact:
                for field, value in six.iteritems(local_kwargs):
                    setattr(contact, field, value)
                contact.is_active = True
                contact.save()
            else:
                contact = Contact.objects.create(**local_kwargs)

        #contact = Contact.objects.filter(org=org, uuid=message.contact, is_stub=False, is_active=True).first()
        #if not contact:
        #    raise ValueError("Contact does not exist or is a stub")

        r = get_redis_connection()
        with r.lock('org:%d:cases_lock' % org.pk):
            # check for open case with this contact
            existing_open = cls.get_open_for_contact_on(org, contact, timezone.now())
            if existing_open:
                existing_open.is_new = False
                return existing_open

            # check for another case (possibly closed) connected to this message
            existing_for_msg = cls.objects.filter(message_id=message.id).first()
            if existing_for_msg:
                existing_for_msg.is_new = False
                return existing_for_msg

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

        # fetch remote messages for contact
        client = self.org.get_temba_client(api_version=2)
        remote = client.get_messages(contact=self.contact.uuid, after=after, before=before).all()

        local_outgoing = self.outgoing_messages.filter(created_on__gte=after, created_on__lte=before)
        local_by_broadcast = {o.broadcast_id: o for o in local_outgoing}

        # merge remotely fetched and local outgoing messages
        messages = []
        for m in remote:
            m.contact = {'uuid': m.contact.uuid}

            local = local_by_broadcast.pop(m.broadcast, None)
            if local:
                m.sender = local.created_by
            messages.append({'time': m.created_on, 'type': 'M', 'item': RemoteMessage.as_json(m, label_map)})

        for m in local_by_broadcast.values():
            messages.append({'time': m.created_on, 'type': 'M', 'item': m.as_json()})

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
        self.incoming_messages.add(msg)

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

    def as_json(self, full_contact=False):
        return {'id': self.pk,
                'contact': self.contact.as_json(full_contact),
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
