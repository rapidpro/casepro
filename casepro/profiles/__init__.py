from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _


# ================================== Monkey patching for the User class ====================================

def _user_clean(user):
    # we use email for login
    if User.objects.filter(email=user.email).exclude(pk=user.pk).exists():
        raise ValidationError(_("Email address already taken."))

    user.username = user.email

    super(User, user).clean()


def _user_has_profile(user):
    from .models import Profile
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
    if user.has_profile() and user.profile.partner and user.profile.partner.org == org:
        return user.profile.partner
    else:
        return None


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


def _user_remove_from_org(user, org):
    # remove user from all org groups
    org.administrators.remove(user)
    org.editors.remove(user)
    org.viewers.remove(user)

    # remove from any partner for this org
    if user.profile.partner and user.profile.partner.org == org:
        user.profile.partner = None
        user.profile.save(update_fields=('partner',))

    # remove as watcher of any case in this org
    for case in user.watched_cases.filter(org=org):
        case.unwatch(user)

    # remove as watcher of any label in this org
    for label in user.watched_labels.filter(org=org):
        label.unwatch(user)


def _user_unicode(user):
    if user.has_profile():
        if user.profile.full_name:
            return '%s (%s)' % (user.profile.full_name, user.email)
    else:
        return user.username  # superuser

    return user.email or user.username


def _user_as_json(user, full=True, org=None):
    if full:
        if org and user.has_profile():
            role_json = user.profile.get_role(org)
            partner_json = user.profile.partner.as_json(full=False) if user.profile.partner else None
        else:
            role_json = None
            partner_json = None

        return {
            'id': user.pk,
            'name': user.get_full_name(),
            'email': user.email,
            'role': role_json,
            'partner': partner_json
        }
    else:
        return {'id': user.pk, 'name': user.get_full_name()}


User.clean = _user_clean
User.has_profile = _user_has_profile
User.get_full_name = _user_get_full_name
User.get_partner = _user_get_partner
User.can_administer = _user_can_administer
User.can_manage = _user_can_manage
User.can_edit = _user_can_edit
User.remove_from_org = _user_remove_from_org
User.__unicode__ = _user_unicode
User.as_json = _user_as_json
