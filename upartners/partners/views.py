from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgObjPermsMixin, OrgPermsMixin
from django import forms
from django.utils.translation import ugettext_lazy as _
from smartmin.users.views import SmartCRUDL, SmartCreateView, SmartListView, SmartReadView, SmartUpdateView
from upartners.partners.models import Partner


class PartnerForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')
        super(PartnerForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Partner
        fields = ('name',)


class PartnerFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(PartnerFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.user.get_org()
        return kwargs


class PartnerCRUDL(SmartCRUDL):
    actions = ('create', 'read', 'update', 'list')
    model = Partner

    class Create(OrgPermsMixin, PartnerFormMixin, SmartCreateView):
        form_class = PartnerForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            self.object = Partner.create(org, data['name'])

    class Update(OrgObjPermsMixin, PartnerFormMixin, SmartUpdateView):
        form_class = PartnerForm

    class Read(OrgObjPermsMixin, SmartReadView):
        def get_context_data(self, **kwargs):
            context = super(PartnerCRUDL.Read, self).get_context_data(**kwargs)
            context['labels'] = self.object.get_labels()
            context['managers'] = self.object.get_managers()
            context['analysts'] = self.object.get_analysts()
            return context

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'labels')
        default_order = ('name',)

        def derive_queryset(self, **kwargs):
            qs = super(PartnerCRUDL.List, self).derive_queryset(**kwargs)
            qs = qs.filter(org=self.request.org)
            return qs

        def get_labels(self, obj):
            return ", ".join([l.name for l in obj.get_labels()])
