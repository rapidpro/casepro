from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Partner

from .models import PARTNER_ROLES, ROLE_ORG_CHOICES, ROLE_PARTNER_CHOICES


class UserForm(forms.ModelForm):
    """
    Base form for all user editing and used for user-editing outside of orgs by superusers
    """

    name = forms.CharField(label=_("Name"), max_length=128)

    email = forms.CharField(label=_("Email"), max_length=254, help_text=_("Email address and login."))

    current_password = forms.CharField(label=_("Current Password"), widget=forms.PasswordInput, required=False)

    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput,
        validators=[validate_password],
        help_text=_("Password used to log in."),
    )

    new_password = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput,
        required=False,
        validators=[validate_password],
        help_text=_("Password used to log in."),
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

    def __init__(self, org, user, *args, **kwargs):
        self.org = org
        self.user = user

        require_password_change = kwargs.pop("require_password_change", False)

        super(UserForm, self).__init__(*args, **kwargs)

        self.fields["new_password"].required = require_password_change

    def clean(self):
        cleaned_data = super(UserForm, self).clean()

        # if a user is updating their own password, need to provide current password
        new_password = cleaned_data.get("new_password")
        if new_password and self.instance == self.user:
            current_password = cleaned_data.get("current_password", "")
            if not self.instance.check_password(current_password):
                self.add_error("current_password", _("Please enter your current password."))

        # if creating new user with password or updating password of existing user, confirmation must match
        password = cleaned_data.get("password") or cleaned_data.get("new_password")
        if password:
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
