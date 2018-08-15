from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Partner

from .models import PARTNER_ROLES, ROLE_ORG_CHOICES, ROLE_PARTNER_CHOICES

MIN_PASSWORD_LENGTH = 10


class PasswordValidator(object):
    """
    Basic password complexity check - should integrate with auth's validate_password functionality when we update to
    Django 1.9.
    """

    def __call__(self, value):
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValidationError(_("Must be at least %d characters long") % MIN_PASSWORD_LENGTH)


class UserForm(forms.ModelForm):
    """
    Base form for all user editing and used for user-editing outside of orgs by superusers
    """

    PASSWORD_FIELD_HELP = _("Password used to log in (minimum of %d characters).") % MIN_PASSWORD_LENGTH

    name = forms.CharField(label=_("Name"), max_length=128)

    email = forms.CharField(label=_("Email"), max_length=254, help_text=_("Email address and login."))

    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput,
        validators=[PasswordValidator()],
        help_text=PASSWORD_FIELD_HELP,
    )

    new_password = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput,
        required=False,
        validators=[PasswordValidator()],
        help_text=PASSWORD_FIELD_HELP,
    )

    confirm_password = forms.CharField(label=_("Confirm password"), widget=forms.PasswordInput, required=False)

    change_password = forms.BooleanField(
        label=_("Require change"), required=False, help_text=_("Whether user must change password on next login.")
    )

    must_use_faq = forms.BooleanField(
        label=_("Pre-approved responses only"),
        required=False,
        help_text=_("Whether user will only be able to reply using pre-approved replies (FAQs)"),
    )

    def __init__(self, *args, **kwargs):
        self.org = kwargs.pop("org")
        require_password_change = kwargs.pop("require_password_change", False)

        super(UserForm, self).__init__(*args, **kwargs)

        self.fields["new_password"].required = require_password_change

    def clean(self):
        cleaned_data = super(UserForm, self).clean()

        password = cleaned_data.get("password") or cleaned_data.get("new_password")
        if password:
            # check that provided password matches confirmation
            confirm_password = cleaned_data.get("confirm_password", "")
            if password != confirm_password:
                self.add_error("confirm_password", _("Passwords don't match."))

        return cleaned_data

    class Meta:
        model = User
        exclude = ()


class OrgUserForm(UserForm):
    """
    Form for user editing at org-level
    """

    role = forms.ChoiceField(label=_("Role"), choices=ROLE_ORG_CHOICES, required=True)

    partner = forms.ModelChoiceField(label=_("Partner Organization"), queryset=Partner.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super(OrgUserForm, self).__init__(*args, **kwargs)

        self.fields["partner"].queryset = Partner.get_all(self.org).order_by("name")

    def clean(self):
        cleaned_data = super(OrgUserForm, self).clean()

        if cleaned_data.get("role") in PARTNER_ROLES and not cleaned_data.get("partner"):
            self.add_error("partner", _("Required for role."))


class PartnerUserForm(UserForm):
    """
    Form for user editing at partner-level
    """

    role = forms.ChoiceField(label=_("Role"), choices=ROLE_PARTNER_CHOICES, required=True)
