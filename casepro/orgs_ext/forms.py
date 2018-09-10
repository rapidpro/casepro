from dash.orgs.models import Org
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from timezone_field import TimeZoneFormField

from casepro.contacts.models import Field, Group


class OrgForm(forms.ModelForm):
    """
    Form for superusers to create and update orgs
    """

    language = forms.ChoiceField(required=False, choices=[("", "")] + list(settings.LANGUAGES))

    timezone = TimeZoneFormField()

    administrators = forms.ModelMultipleChoiceField(queryset=User.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super(OrgForm, self).__init__(*args, **kwargs)
        administrators = User.objects.exclude(profile=None).order_by("profile__full_name")

        self.fields["administrators"].queryset = administrators

    class Meta:
        model = Org
        fields = forms.ALL_FIELDS


class OrgEditForm(forms.ModelForm):
    """
    Form for org admins to update their own org
    """

    name = forms.CharField(label=_("Organization"), help_text=_("The name of this organization"))

    timezone = TimeZoneFormField(help_text=_("The timezone your organization is in"))

    banner_text = forms.CharField(
        label=_("Banner text"),
        widget=forms.Textarea,
        help_text=_("Banner text displayed to all users"),
        required=False,
    )

    contact_fields = forms.MultipleChoiceField(
        choices=(), label=_("Contact fields"), help_text=_("Contact fields to display"), required=False
    )

    suspend_groups = forms.MultipleChoiceField(
        choices=(),
        label=_("Suspend groups"),
        help_text=_("Groups to remove contacts from when creating cases"),
        required=False,
    )

    followup_flow = forms.ChoiceField(
        choices=(),
        label=_("Follow-up Flow"),
        help_text=_("Flow to start after a case is closed"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        org = kwargs.pop("org")
        super(OrgEditForm, self).__init__(*args, **kwargs)

        self.fields["banner_text"].initial = org.get_banner_text()

        field_choices = []
        for field in Field.objects.filter(org=org, is_active=True).order_by("label"):
            field_choices.append((field.pk, "%s (%s)" % (field.label, field.key)))

        self.fields["contact_fields"].choices = field_choices
        self.fields["contact_fields"].initial = [f.pk for f in Field.get_all(org, visible=True)]

        group_choices = []
        for group in Group.get_all(org, dynamic=False).order_by("name"):
            group_choices.append((group.pk, group.name))

        self.fields["suspend_groups"].choices = group_choices
        self.fields["suspend_groups"].initial = [g.pk for g in Group.get_suspend_from(org)]

        flow_choices = [('', '----')]
        for flow in org.get_backend().fetch_flows(org):
            flow_choices.append((flow.uuid, flow.name))

        flow_initial = org.get_followup_flow()

        self.fields["followup_flow"].choices = flow_choices
        if flow_initial:
            self.fields["followup_flow"].initial = flow_initial.uuid

    class Meta:
        model = Org
        fields = ("name", "timezone", "banner_text", "contact_fields", "suspend_groups", "followup_flow", "logo")
