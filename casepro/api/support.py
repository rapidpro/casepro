from rest_framework import permissions, views


class AdministratorPermission(permissions.BasePermission):
    message = "Must be an administrator."

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and not user.is_anonymous and user.can_administer(request.org)


def get_view_name(view_cls, suffix=None):
    if hasattr(view_cls, "title"):
        return view_cls.title

    return views.get_view_name(view_cls, suffix)
