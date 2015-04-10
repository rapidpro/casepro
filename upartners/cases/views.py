from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin
from django.http import JsonResponse
from smartmin.users.views import SmartCRUDL, SmartFormView
from .models import Case


class CaseCRUDL(SmartCRUDL):
    model = Case
    actions = ('create',)

    class Create(OrgPermsMixin, SmartFormView):
        fields = ('labels', 'contact_uuid')

        def form_valid(self, form):
            labels = form.cleaned_data['labels']
            partner = self.request.user.profile.partner
            contact_uuid = form.cleaned_data['contact_uuid']

            case = Case.open(self.request.org, self.request.user, labels, partner, contact_uuid)

            return JsonResponse(dict(case_id=case.pk))



