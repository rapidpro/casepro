from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _

from casepro.msgs.models import Label

from .models import Partner


class PartnerForm(forms.ModelForm):
    labels = forms.ModelMultipleChoiceField(label=_("Can Access"), queryset=Label.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')
        super(PartnerForm, self).__init__(*args, **kwargs)

        self.fields['labels'].queryset = Label.get_all(org)

    class Meta:
        model = Partner
        fields = ('name', 'logo', 'labels')
