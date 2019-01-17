from rest_framework import permissions, views


class AdministratorPermission(permissions.BasePermission):
    message = "Must be an administrator."

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and not user.is_anonymous and user.can_administer(request.org)
