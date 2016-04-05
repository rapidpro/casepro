from __future__ import unicode_literals

from dash.orgs.models import Org
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from timezones.forms import TimeZoneField


class OrgForm(forms.ModelForm):
    language = forms.ChoiceField(required=False, choices=[('', '')] + list(settings.LANGUAGES))
    timezone = TimeZoneField()

    def __init__(self, *args, **kwargs):
        super(OrgForm, self).__init__(*args, **kwargs)
        administrators = User.objects.exclude(profile=None).order_by('profile__full_name')

        self.fields['administrators'].queryset = administrators

    class Meta:
        model = Org
        fields = forms.ALL_FIELDS
