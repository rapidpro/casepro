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
ACTION_ADD_NOTE = 'N'
ACTION_REASSIGN = 'A'
ACTION_CLOSE = 'C'
ACTION_REOPEN = 'R'

CASE_ACTION_CHOICES = ((ACTION_OPEN, _("Open")),
                       (ACTION_ADD_NOTE, _("Add Note")),
                       (ACTION_REASSIGN, _("Reassign")),
                       (ACTION_CLOSE, _("Close")),
                       (ACTION_REOPEN, _("Reopen")))


class Case(models.Model):
    """
    A case between a partner organization and a contact
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='cases')

    labels = models.ManyToManyField(Label, verbose_name=_("Labels"), related_name='cases')

    partner = models.ForeignKey(Partner, related_name="cases")

    contact_uuid = models.CharField(max_length=36)

    opened_on = models.DateTimeField(auto_now_add=True,
                                     help_text="When this case was opened")

    closed_on = models.DateTimeField(null=True,
                                     help_text="When this case was closed")

    @classmethod
    def open(cls, org, user, labels, partner, contact_uuid):
        case = cls.objects.create(org=org, partner=partner, contact_uuid=contact_uuid)
        case.labels.add(*labels)

        CaseAction.create(case, user, ACTION_OPEN, assignee=partner)
        return case

    def add_note(self, user, text):
        CaseAction.create(self, user, ACTION_ADD_NOTE, note=text)

    def close(self, user):
        if not self._can_edit(user):
            raise PermissionDenied()

        self.closed_on = timezone.now()
        self.save(update_fields=('closed_on',))

        CaseAction.create(self, user, ACTION_CLOSE)

    def reopen(self, user):
        if not self._can_edit(user):
            raise PermissionDenied()

        self.closed_on = None
        self.save(update_fields=('closed_on',))

        CaseAction.create(self, user, ACTION_REOPEN)

    def reassign(self, user, partner):
        if not self._can_edit(user):
            raise PermissionDenied()

        self.partner = partner
        self.save(update_fields=('partner',))

        CaseAction.create(self, user, ACTION_REASSIGN, assignee=partner)

    def _can_edit(self, user):
        if user.is_admin_for(self.org):
            return True

        return user.has_profile() and user.profile.partner == self.partner

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


class CaseAction(models.Model):
    case = models.ForeignKey(Case, related_name="history")

    action = models.CharField(max_length=1, choices=CASE_ACTION_CHOICES)

    performed_by = models.ForeignKey(User, related_name="case_actions")

    performed_on = models.DateTimeField(auto_now_add=True)

    assignee = models.ForeignKey(Partner, null=True, related_name="case_actions")

    note = models.CharField(null=True, max_length=1024)

    @classmethod
    def create(cls, case, user, action, assignee=None, note=None):
        CaseAction.objects.create(case=case, action=action, performed_by=user, assignee=assignee, note=note)

    class Meta:
        ordering = ('pk',)
