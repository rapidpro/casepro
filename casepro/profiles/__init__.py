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
        if role == ROLE_ANALYST:
            org.viewers.add(user)
        elif role == ROLE_MANAGER:
            org.editors.add(user)
        else:  # pragma: no cover
            raise ValueError("Invalid user role: %s" % role)

    return user


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


def _user_is_admin_for(user, org):
    """
    Whether this user is an administrator for the given org
    """
    return org.administrators.filter(pk=user.pk).exists()


def _user_unicode(user):
    if user.has_profile():
        if user.profile.full_name:
            return user.profile.full_name
    else:
        return user.username  # superuser

    return user.email or user.username


User.create = classmethod(_user_create)
User.clean = _user_clean
User.has_profile = _user_has_profile
User.get_full_name = _user_get_full_name
User.get_partner = _user_get_partner
User.is_admin_for = _user_is_admin_for
User.__unicode__ = _user_unicode
