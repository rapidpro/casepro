from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgObjPermsMixin, OrgPermsMixin
from django import forms
from django.utils.translation import ugettext_lazy as _
from smartmin.users.views import SmartCRUDL, SmartCreateView, SmartListView, SmartUpdateView
from upartners.labels.models import Label
from upartners.partners.models import Partner


class PartnerForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)

    labels = forms.ModelMultipleChoiceField(label=_("Labels"), queryset=Label.objects.none())

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')

        super(PartnerForm, self).__init__(*args, **kwargs)

        self.fields['labels'].queryset = Label.get_all(org)

    class Meta:
        model = Label
        fields = ('name', 'labels')


class PartnerFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(PartnerFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.user.get_org()
        return kwargs


class PartnerCRUDL(SmartCRUDL):
    actions = ('create', 'update', 'list')
    model = Partner

    class Create(OrgPermsMixin, PartnerFormMixin, SmartCreateView):
        form_class = PartnerForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            name = data['name']
            labels = data['labels']
            self.object = Partner.create(org, name, labels)

    class Update(OrgObjPermsMixin, PartnerFormMixin, SmartUpdateView):
        form_class = PartnerForm

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'labels')
        default_order = ('name',)

        def derive_queryset(self, **kwargs):
            qs = super(PartnerCRUDL.List, self).derive_queryset(**kwargs)
            qs = qs.filter(org=self.request.org)
            return qs

        def get_labels(self, obj):
            return ",".join([l.name for l in obj.get_labels()])
