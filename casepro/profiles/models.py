from __future__ import absolute_import, unicode_literals

import six

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import CaseAction, Partner
from casepro.msgs.models import Message
from casepro.utils.email import send_email

ROLE_ADMIN = 'A'
ROLE_MANAGER = 'M'
ROLE_ANALYST = 'Y'

ROLE_ORG_CHOICES = ((ROLE_ADMIN, _("Administrator")),
                    (ROLE_MANAGER, _("Partner Manager")),
                    (ROLE_ANALYST, _("Partner Data Analyst")))
ROLE_PARTNER_CHOICES = ((ROLE_MANAGER, _("Manager")),
                        (ROLE_ANALYST, _("Data Analyst")))

PARTNER_ROLES = {ROLE_MANAGER, ROLE_ANALYST}  # roles that are tied to a partner


class Profile(models.Model):
    """
    Extension for the user class
    """
    user = models.OneToOneField(User)

    partner = models.ForeignKey(Partner, null=True, related_name='user_profiles')

    full_name = models.CharField(verbose_name=_("Full name"), max_length=128, null=True)

    change_password = models.BooleanField(default=False, help_text=_("User must change password on next login"))

    @classmethod
    def create_user(cls, name, email, password, change_password=False):
        """
        Creates an un-attached user
        """
        # create auth user
        user = User.objects.create(username=email, email=email, is_active=True)
        user.set_password(password)
        user.save()

        # add profile
        cls.objects.create(user=user, full_name=name, change_password=change_password)

        return user

    @classmethod
    def create_org_user(cls, org, name, email, password, change_password=False):
        """
        Creates an org-level user (for now these are always admins)
        """
        user = cls.create_user(name, email, password, change_password=change_password)
        user.profile.update_role(org, ROLE_ADMIN)
        return user

    @classmethod
    def create_partner_user(cls, org, partner, role, name, email, password, change_password=False):
        """
        Creates a partner-level user
        """
        if not partner or partner.org != org:  # pragma: no cover
            raise ValueError("Can't create partner user without valid partner for org")

        user = cls.create_user(name, email, password, change_password=change_password)
        user.profile.update_role(org, role, partner)
        return user

    def update_role(self, org, role, partner=None):
        if partner and partner.org != org:  # pragma: no cover
            raise ValueError("Can only update partner to partner in same org")

        if role in PARTNER_ROLES and not partner:
            raise ValueError("Role %s requires a partner org" % role)
        elif role not in PARTNER_ROLES and partner:
            raise ValueError("Cannot specify a partner for role %s" % role)

        self.partner = partner
        self.save(update_fields=('partner',))

        if role == ROLE_ADMIN:
            org.administrators.add(self.user)
            org.editors.remove(self.user)
            org.viewers.remove(self.user)
        elif role == ROLE_MANAGER:
            org.administrators.remove(self.user)
            org.editors.add(self.user)
            org.viewers.remove(self.user)
        elif role == ROLE_ANALYST:
            org.administrators.remove(self.user)
            org.editors.remove(self.user)
            org.viewers.add(self.user)
        else:  # pragma: no cover
            raise ValueError("Invalid user role: %s" % role)

    def get_role(self, org):
        if self.user in org.administrators.all():
            return ROLE_ADMIN
        elif self.user in org.editors.all():
            return ROLE_MANAGER
        elif self.user in org.viewers.all():
            return ROLE_ANALYST
        else:
            return None

    @classmethod
    def exists_for(cls, user):
        try:
            return bool(user.profile)
        except Profile.DoesNotExist:
            return False


class Notification(models.Model):
    """
    A notification sent to a user
    """
    TYPE_MESSAGE_LABELLING = 'L'
    TYPE_CASE_ACTION = 'A'
    TYPE_CASE_REPLY = 'R'

    TYPE_NAME = {
        TYPE_MESSAGE_LABELLING: 'message_labelling',
        TYPE_CASE_ACTION: 'case_action',
        TYPE_CASE_REPLY: 'case_reply',
    }

    user = models.ForeignKey(User, related_name='notifications')

    type = models.CharField(max_length=1)

    message = models.ForeignKey(Message, null=True)

    case_action = models.ForeignKey(CaseAction, null=True)

    is_sent = models.BooleanField(default=False)

    created_on = models.DateTimeField(default=timezone.now)

    @classmethod
    def new_message_labelling(cls, user, message):
        return cls.objects.get_or_create(user=user, type=cls.TYPE_MESSAGE_LABELLING, message=message)

    @classmethod
    def new_case_action(cls, user, case_action):
        return cls.objects.get_or_create(user=user, type=cls.TYPE_CASE_ACTION, case_action=case_action)

    @classmethod
    def new_case_reply(cls, user, message):
        return cls.objects.get_or_create(user=user, type=cls.TYPE_CASE_REPLY, message=message)

    @classmethod
    def send_all(cls):
        unsent = cls.objects.filter(is_sent=False).order_by('created_on')

        for notification in unsent:
            type_name = cls.TYPE_NAME[notification.type]
            subject, template, context = getattr(notification, '_build_%s_email' % type_name)()
            template_path = 'profiles/email/%s' % template

            send_email([notification.user], six.text_type(subject), template_path, context)

        unsent.update(is_sent=True)

    def _build_message_labelling_email(self):
        context = {
            'labels': set(self.user.watched_labels.all()).intersection(self.message.labels.all()),
            'inbox_url': self.message.org.make_absolute_url(reverse('cases.inbox'))
        }
        return _("New labelled message"), 'message_labelling', context

    def _build_case_action_email(self):
        context = {
            'case_url': self.message.org.make_absolute_url(reverse('cases.case_read', args=[self.pk])),
            'user': self.case_action.created_by,
            'note': self.case_action.note,
            'assignee': self.case_action.assignee
        }

        if self.case_action.action == CaseAction.ADD_NOTE:
            subject = _("New note in case #%d") % self.case.pk
            template = 'case_new_note'
        elif self.case_action.action == CaseAction.CLOSE:
            subject = _("Case #%d was closed") % self.case.pk
            template = 'case_closed'
        elif self.case_action.action == CaseAction.REOPEN:
            subject = _("Case #%d was reopened") % self.case.pk
            template = 'case_reopened'
        elif self.case_action.action == CaseAction.REASSIGN:
            subject = _("Case #%d was reassigned") % self.case.pk
            template = 'case_reassigned'
        else:  # pragma: no cover
            raise ValueError("Notifications not supported for case action type %s" % self.case_action.action)

        return subject, template, context

    def _build_case_reply_email(self):
        context = {
            'case_url': self.message.org.make_absolute_url(reverse('cases.case_read', args=[self.pk]))
        }
        return _("New reply in case #%d") % self.case.pk, 'case_reply', context
