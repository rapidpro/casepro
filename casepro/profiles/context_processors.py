from __future__ import absolute_import, unicode_literals


def user_is_admin(request):
    """
    Context processor that adds boolean of whether current user is an admin for current org
    """
    is_admin = request.org and not request.user.is_anonymous() and request.user.can_administer(request.org)

    return {'user_is_admin': is_admin}
