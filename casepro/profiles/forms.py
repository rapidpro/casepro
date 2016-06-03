from __future__ import unicode_literals

from django import forms
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Partner

from .models import ROLE_ANALYST, ROLE_PARTNER_CHOICES


class UserForm(forms.ModelForm):
    """
    Form for user profiles
    """
    full_name = forms.CharField(label=_("Full name"), max_length=128)

    role = forms.ChoiceField(label=_("Role"), choices=ROLE_PARTNER_CHOICES, required=True, initial=ROLE_ANALYST)

    partner = forms.ModelChoiceField(label=_("Partner Organization"), queryset=Partner.objects.none())

    email = forms.CharField(label=_("Email"), max_length=254,
                            help_text=_("Email address and login."))

    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput, validators=[MinLengthValidator(8)],
                               help_text=_("Password used to log in (minimum of 8 characters)."))

    new_password = forms.CharField(widget=forms.PasswordInput, validators=[MinLengthValidator(8)], required=False,
                                   label=_("New password"),
                                   help_text=_("Password used to login (minimum of 8 characters, optional)."))

    confirm_password = forms.CharField(label=_("Confirm password"), widget=forms.PasswordInput, required=False)

    change_password = forms.BooleanField(label=_("Require change"), required=False,
                                         help_text=_("Whether user must change password on next login."))

    def __init__(self, *args, **kwargs):
        self.org = kwargs.pop('org')

        super(UserForm, self).__init__(*args, **kwargs)

        self.fields['partner'].queryset = Partner.get_all(self.org).order_by('name')

    def clean(self):
        cleaned_data = super(UserForm, self).clean()

        password = cleaned_data.get('password', None) or cleaned_data.get('new_password', None)
        if password:
            confirm_password = cleaned_data.get('confirm_password', '')
            if password != confirm_password:
                self.add_error('confirm_password', _("Passwords don't match."))

    class Meta:
        model = User
        exclude = ()
