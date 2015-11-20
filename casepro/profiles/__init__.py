from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from .models import Profile


ROLE_ANALYST = 'A'
ROLE_MANAGER = 'M'

ROLE_CHOICES = ((ROLE_ANALYST, _("Data Analyst")), (ROLE_MANAGER, _("Manager")))


# ================================== Monkey patching for the User class ====================================

def _user_create(cls, org, partner, role, full_name, email, password, change_password=False):
    """
    Creates a user
    """
    if role and (not org or not partner):  # pragma: no cover
        raise ValueError("Only users in partner organizations can be assigned a role")

    if partner and partner.org_id != org.pk:  # pragma: no cover
        raise ValueError("Org and partner org mismatch")

    # create auth user
    user = cls.objects.create(is_active=True, username=email, email=email)
    user.set_password(password)
    user.save()

    # add profile
    Profile.objects.create(user=user, partner=partner, full_name=full_name, change_password=change_password)

    if org:
        user.update_role(org, role)

    return user


def _user_update_role(user, org, role):
    if role == ROLE_ANALYST:
        org.viewers.add(user)
        org.editors.remove(user)
    elif role == ROLE_MANAGER:
        org.viewers.remove(user)
        org.editors.add(user)
    else:  # pragma: no cover
        raise ValueError("Invalid user role: %s" % role)


def _user_clean(user):
    # we use email for login
    if User.objects.filter(email=user.email).exclude(pk=user.pk).exists():
        raise ValidationError(_("Email address already taken."))

    user.username = user.email

    super(User, user).clean()


def _user_has_profile(user):
    try:
        return bool(user.profile)
    except Profile.DoesNotExist:
        return False


def _user_get_full_name(user):
    """
    Override regular get_full_name which returns first_name + last_name
    """
    return user.profile.full_name if user.has_profile() else " ".join([user.first_name, user.last_name]).strip()


def _user_get_partner(user):
    return user.profile.partner if user.has_profile() else None


def _user_can_administer(user, org):
    """
    Whether this user can administer the given org
    """
    return user.is_superuser or org.administrators.filter(pk=user.pk).exists()


def _user_can_manage(user, partner):
    """
    Whether this user can manage the given partner org
    """
    if user.can_administer(partner.org):
        return True

    return user.get_partner() == partner and partner.org.editors.filter(pk=user.pk).exists()


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

    other_partner = other.get_partner()
    return other_partner and user.can_manage(other_partner)  # manager can edit users in same partner org


def _user_release(user):
    user.is_active = False
    user.save(update_fields=('is_active',))


def _user_unicode(user):
    if user.has_profile():
        if user.profile.full_name:
            return '%s (%s)' % (user.profile.full_name, user.email)
    else:
        return user.username  # superuser

    return user.email or user.username


def _user_as_json(user):
    return {'id': user.pk, 'name': user.get_full_name()}


User.create = classmethod(_user_create)
User.update_role = _user_update_role
User.clean = _user_clean
User.has_profile = _user_has_profile
User.get_full_name = _user_get_full_name
User.get_partner = _user_get_partner
User.can_administer = _user_can_administer
User.can_manage = _user_can_manage
User.can_edit = _user_can_edit
User.release = _user_release
User.__unicode__ = _user_unicode
User.as_json = _user_as_json
