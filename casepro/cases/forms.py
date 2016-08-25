from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _
from casepro.msgs.models import Label

from .models import Partner


class PartnerUpdateForm(forms.ModelForm):
    labels = forms.ModelMultipleChoiceField(label=_("Can Access"),
                                            queryset=Label.objects.none(),
                                            widget=forms.CheckboxSelectMultiple(),
                                            required=False)

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')
        super(PartnerUpdateForm, self).__init__(*args, **kwargs)

        self.fields['primary_contact'].queryset = kwargs['instance'].get_users()
        self.fields['labels'].queryset = Label.get_all(org).order_by('name')

    class Meta:
        model = Partner
        fields = ('name', 'description', 'primary_contact', 'logo', 'is_restricted', 'labels')


class PartnerCreateForm(forms.ModelForm):
    labels = forms.ModelMultipleChoiceField(label=_("Can Access"),
                                            queryset=Label.objects.none(),
                                            widget=forms.CheckboxSelectMultiple(),
                                            required=False)

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')
        super(PartnerCreateForm, self).__init__(*args, **kwargs)

        self.fields['labels'].queryset = Label.get_all(org).order_by('name')

    class Meta:
        model = Partner
        fields = ('name', 'description', 'logo', 'is_restricted', 'labels')
