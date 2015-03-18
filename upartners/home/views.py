from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin
from django.utils.translation import ugettext_lazy as _
from smartmin.users.views import SmartTemplateView
from upartners.labels.models import Label


class HomeView(OrgPermsMixin, SmartTemplateView):
    """
    Homepage
    """
    title = _("Home")
    template_name = 'home/home.haml'

    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        context['labels'] = Label.get_all(self.request.org, with_counts=True).order_by('name')
        return context
