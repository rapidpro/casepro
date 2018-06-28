from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import CaseAction
from casepro.msgs.models import Message
from casepro.utils.email import send_email

ROLE_ADMIN = "A"
ROLE_MANAGER = "M"
ROLE_ANALYST = "Y"

ROLE_ORG_CHOICES = (
    (ROLE_ADMIN, _("Administrator")),
    (ROLE_MANAGER, _("Partner Manager")),
    (ROLE_ANALYST, _("Partner Data Analyst")),
)
ROLE_PARTNER_CHOICES = ((ROLE_MANAGER, _("Manager")), (ROLE_ANALYST, _("Data Analyst")))

PARTNER_ROLES = {ROLE_MANAGER, ROLE_ANALYST}  # roles that are tied to a partner


class Profile(models.Model):
    """
    Extension for the user class
    """
    user = models.OneToOneField(User)

    full_name = models.CharField(verbose_name=_("Full name"), max_length=128, null=True)

    change_password = models.BooleanField(default=False, help_text=_("User must change password on next login"))

    must_use_faq = models.BooleanField(
        default=False, help_text=_("User is only allowed to reply with pre-approved responses")
    )

    @classmethod
    def create_user(cls, name, email, password, change_password=False, must_use_faq=False):
        """
        Creates an un-attached user
        """
        # create auth user
        user = User.objects.create(username=email, email=email, is_active=True)
        user.set_password(password)
        user.save()

        # add profile
        cls.objects.create(user=user, full_name=name, change_password=change_password, must_use_faq=must_use_faq)

        return user

    @classmethod
    def create_org_user(cls, org, name, email, password, change_password=False, must_use_faq=False):
        """
        Creates an org-level user (for now these are always admins)
        """
        user = cls.create_user(name, email, password, change_password=change_password, must_use_faq=must_use_faq)
        user.update_role(org, ROLE_ADMIN)
        return user

    @classmethod
    def create_partner_user(cls, org, partner, role, name, email, password, change_password=False, must_use_faq=False):
        """
        Creates a partner-level user
        """
        if not partner or partner.org != org:  # pragma: no cover
            raise ValueError("Can't create partner user without valid partner for org")

        user = cls.create_user(name, email, password, change_password=change_password, must_use_faq=must_use_faq)
        user.update_role(org, role, partner)
        return user

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
    TYPE_MESSAGE_LABELLING = "L"
    TYPE_CASE_ASSIGNMENT = "C"
    TYPE_CASE_ACTION = "A"
    TYPE_CASE_REPLY = "R"

    TYPE_NAME = {
        TYPE_MESSAGE_LABELLING: "message_labelling",
        TYPE_CASE_ASSIGNMENT: "case_assignment",
        TYPE_CASE_ACTION: "case_action",
        TYPE_CASE_REPLY: "case_reply",
    }

    org = models.ForeignKey(Org)

    user = models.ForeignKey(User, related_name="notifications")

    type = models.CharField(max_length=1)

    message = models.ForeignKey(Message, null=True)

    case_action = models.ForeignKey(CaseAction, null=True)

    is_sent = models.BooleanField(default=False)

    created_on = models.DateTimeField(default=timezone.now)

    @classmethod
    def new_message_labelling(cls, org, user, message):
        return cls.objects.get_or_create(org=org, user=user, type=cls.TYPE_MESSAGE_LABELLING, message=message)

    @classmethod
    def new_case_assignment(cls, org, user, case_action):
        return cls.objects.get_or_create(org=org, user=user, type=cls.TYPE_CASE_ASSIGNMENT, case_action=case_action)

    @classmethod
    def new_case_action(cls, org, user, case_action):
        return cls.objects.get_or_create(org=org, user=user, type=cls.TYPE_CASE_ACTION, case_action=case_action)

    @classmethod
    def new_case_reply(cls, org, user, message):
        return cls.objects.get_or_create(org=org, user=user, type=cls.TYPE_CASE_REPLY, message=message)

    @classmethod
    def send_all(cls):
        unsent = cls.objects.filter(is_sent=False)
        unsent = unsent.select_related("org", "user", "message", "case_action").order_by("created_on")

        for notification in unsent:
            type_name = cls.TYPE_NAME[notification.type]
            subject, template, context = getattr(notification, "_build_%s_email" % type_name)()
            template_path = "profiles/email/%s" % template

            send_email([notification.user], str(subject), template_path, context)

        unsent.update(is_sent=True)

    def _build_message_labelling_email(self):
        context = {
            "labels": set(self.user.watched_labels.all()).intersection(self.message.labels.all()),
            "inbox_url": self.org.make_absolute_url(reverse("cases.inbox")),
        }
        return _("New labelled message"), "message_labelling", context

    def _build_case_assignment_email(self):
        case = self.case_action.case
        context = {
            "user": self.case_action.created_by,
            "case_url": self.org.make_absolute_url(reverse("cases.case_read", args=[case.pk])),
        }
        return _("New case assignment #%d") % case.pk, "case_assignment", context

    def _build_case_action_email(self):
        case = self.case_action.case
        context = {
            "user": self.case_action.created_by,
            "note": self.case_action.note,
            "assignee": self.case_action.assignee,
            "case_url": self.org.make_absolute_url(reverse("cases.case_read", args=[case.pk])),
        }

        if self.case_action.action == CaseAction.ADD_NOTE:
            subject = _("New note in case #%d") % case.pk
            template = "case_new_note"
        elif self.case_action.action == CaseAction.CLOSE:
            subject = _("Case #%d was closed") % case.pk
            template = "case_closed"
        elif self.case_action.action == CaseAction.REOPEN:
            subject = _("Case #%d was reopened") % case.pk
            template = "case_reopened"
        elif self.case_action.action == CaseAction.REASSIGN:
            subject = _("Case #%d was reassigned") % case.pk
            template = "case_reassigned"
        else:  # pragma: no cover
            raise ValueError("Notifications not supported for case action type %s" % self.case_action.action)

        return subject, template, context

    def _build_case_reply_email(self):
        case = self.message.case
        context = {"case_url": self.org.make_absolute_url(reverse("cases.case_read", args=[case.pk]))}
        return _("New reply in case #%d") % case.pk, "case_reply", context


# ================================== Monkey patching for the User class ====================================


def _user_clean(user):
    # we use email for login
    if User.objects.filter(email=user.email).exclude(pk=user.pk).exists():
        raise ValidationError(_("Email address already taken."))

    user.username = user.email

    super(User, user).clean()


def _user_has_profile(user):
    return Profile.exists_for(user)


def _user_get_full_name(user):
    """
    Override regular get_full_name which returns first_name + last_name
    """
    return user.profile.full_name if user.has_profile() else " ".join([user.first_name, user.last_name]).strip()


def _user_get_partner(user, org):
    """
    Gets the partner org for this user in the given org
    """
    return user.partners.filter(org=org, is_active=True).first()


def _user_get_role(user, org):
    """
    Gets the role as a character code for this user in the given org
    """
    if user in org.administrators.all():
        return ROLE_ADMIN
    elif user in org.editors.all():
        return ROLE_MANAGER
    elif user in org.viewers.all():
        return ROLE_ANALYST
    else:
        return None


def _user_update_role(user, org, role, partner=None):
    """
    Updates this user's role in the given org
    """
    if partner and partner.org != org:  # pragma: no cover
        raise ValueError("Can only update partner to partner in same org")

    if role in PARTNER_ROLES and not partner:
        raise ValueError("Role %s requires a partner org" % role)
    elif role not in PARTNER_ROLES and partner:
        raise ValueError("Cannot specify a partner for role %s" % role)

    remove_from = [p for p in user.partners_primary.filter(org=org) if p != partner]
    user.partners_primary.remove(*remove_from)

    user.partners.remove(*user.partners.filter(org=org))

    if partner:
        user.partners.add(partner)

    if role == ROLE_ADMIN:
        org.administrators.add(user)
        org.editors.remove(user)
        org.viewers.remove(user)
    elif role == ROLE_MANAGER:
        org.administrators.remove(user)
        org.editors.add(user)
        org.viewers.remove(user)
    elif role == ROLE_ANALYST:
        org.administrators.remove(user)
        org.editors.remove(user)
        org.viewers.add(user)
    else:  # pragma: no cover
        raise ValueError("Invalid user role: %s" % role)


def _user_remove_from_org(user, org):
    # remove user from all org groups
    org.administrators.remove(user)
    org.editors.remove(user)
    org.viewers.remove(user)

    # remove primary_contact fk relationship
    user.partners_primary.remove(*user.partners_primary.filter(org=org))

    # remove user from any partners for this org
    user.partners.remove(*user.partners.filter(org=org))

    # remove as watcher of any case in this org
    for case in user.watched_cases.filter(org=org):
        case.unwatch(user)

    # remove as watcher of any label in this org
    for label in user.watched_labels.filter(org=org):
        label.unwatch(user)


def _user_can_administer(user, org):
    """
    Whether this user can administer the given org
    """
    return user.is_superuser or org.administrators.filter(pk=user.pk).exists()


def _user_can_manage(user, partner):
    """
    Whether this user can manage the given partner org
    """
    org = partner.org

    if user.can_administer(org):
        return True

    return user.get_partner(org) == partner and org.editors.filter(pk=user.pk).exists()


def _user_can_edit(user, org, other):
    """
    Whether or not this user can edit the other user
    """
    if user.is_superuser:
        return True

    other_group = org.get_user_org_group(other)
    if not other_group:  # other user doesn't belong to this org
        return False

    if user.can_administer(org):
        return True

    other_partner = other.get_partner(org)
    return other_partner and user.can_manage(other_partner)  # manager can edit users in same partner org


def _user_must_use_faq(user):
    """
    Whether this user must reply using a pre-approved response (FAQ)
    """
    if user.has_profile():
        return user.profile.must_use_faq
    else:
        return False


def _user_str(user):
    if user.has_profile():
        if user.profile.full_name:
            return "%s (%s)" % (user.profile.full_name, user.email)
    else:
        return user.username  # superuser

    return user.email or user.username


def _user_as_json(user, full=True, org=None):
    if full:
        if org and user.has_profile():
            partner = user.get_partner(org)
            partner_json = partner.as_json(full=False) if partner else None
            role_json = user.get_role(org)
        else:
            role_json = None
            partner_json = None

        return {
            "id": user.pk,
            "name": user.get_full_name(),
            "email": user.email,
            "role": role_json,
            "partner": partner_json,
        }
    else:
        return {"id": user.pk, "name": user.get_full_name()}


User.clean = _user_clean
User.has_profile = _user_has_profile
User.get_full_name = _user_get_full_name
User.get_partner = _user_get_partner
User.get_role = _user_get_role
User.update_role = _user_update_role
User.can_administer = _user_can_administer
User.can_manage = _user_can_manage
User.can_edit = _user_can_edit
User.remove_from_org = _user_remove_from_org
User.as_json = _user_as_json
User.must_use_faq = _user_must_use_faq
User.__str__ = _user_str
