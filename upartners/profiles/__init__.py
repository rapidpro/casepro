from __future__ import absolute_import, unicode_literals

from dash.utils import get_obj_cacheable
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from upartners.partners.models import PARTNER_ANALYST, PARTNER_MANAGER
from .models import Profile


# ================================== Monkey patching for the User class ====================================

def _user_create(cls, org, partner, group, full_name, email, password, change_password=False):
    """
    Creates a user
    """
    # create auth user
    user = cls.objects.create(is_active=True, username=email, email=email)
    user.set_password(password)
    user.save()

    # add profile
    Profile.objects.create(user=user, full_name=full_name, change_password=change_password)

    if partner:
        # setup as partner user login with given group
        if group == PARTNER_ANALYST:
            partner.analysts.add(user)
        elif group == PARTNER_MANAGER:
            partner.managers.add(user)
        else:
            raise ValueError("Invalid partner group")
    elif org:
        # setup as org administrator
        org.administrators.add(org)

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


def _user_is_admin_for(user, org):
    """
    Whether this user is an administrator for the given org
    """
    return org.administrators.filter(pk=user.pk).exists()


def _user_get_partner(user):
    # we could potentially allow users to switch between partner orgs, but for now we assume a user has only one
    return get_obj_cacheable(user, '_partner', lambda: user.manage_partners.first() or user.analyst_partners.first())


def _user_get_group(user, org):
    if user.is_admin_for(org):
        return Group.objects.get(name="Administrators")

    partner = user.get_partner()
    if partner:
        if user in partner.managers.all():
            return Group.objects.get(name="Managers")
        elif user in partner.analysts.all():
            return Group.objects.get(name="Analysts")

    return None


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
User.is_admin_for = _user_is_admin_for
User.get_partner = _user_get_partner
User.get_group = _user_get_group
User.__unicode__ = _user_unicode
