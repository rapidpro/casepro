from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _

ALLOW_NO_CHANGE = {"profiles.user_self", "users.user_logout"}


class ForcePasswordChangeMiddleware(object):
    """
    Middleware to check if logged in user has to change their password
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_anonymous() or not request.user.has_profile():
            return

        if request.user.profile.change_password:
            url_name = request.resolver_match.url_name

            if url_name not in ALLOW_NO_CHANGE:
                messages.info(request, _("You are required to change your password"))
                return HttpResponseRedirect(reverse("profiles.user_self"))
