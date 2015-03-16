from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgObjPermsMixin, OrgPermsMixin
from django.utils.translation import ugettext_lazy as _
from smartmin.users.views import SmartCRUDL, SmartCreateView, SmartListView, SmartUpdateView
from upartners.partners.models import Partner


class PartnerCRUDL(SmartCRUDL):
    actions = ('create', 'update', 'list')
    model = Partner

    class Create(OrgPermsMixin, SmartCreateView):
        fields = ('name', 'labels')

    class Update(OrgObjPermsMixin, SmartUpdateView):
        fields = ('name', 'labels')

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'labels')
