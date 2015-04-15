from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from upartners.labels.models import Label
from upartners.partners.models import Partner


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
