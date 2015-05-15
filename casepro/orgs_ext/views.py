from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from dash.orgs.views import OrgCRUDL, OrgForm, InferOrgMixin, OrgPermsMixin, SmartUpdateView
from dash.utils import ms_to_datetime
from django import forms
from django.utils.translation import ugettext_lazy as _
from smartmin.templatetags.smartmin import format_datetime
from smartmin.users.views import SmartCRUDL
from timezones.forms import TimeZoneField
from . import TaskType


class OrgExtCRUDL(SmartCRUDL):
    actions = ('create', 'update', 'list', 'home', 'edit', 'chooser', 'choose')
    model = Org

    class Create(OrgCRUDL.Create):
        pass

    class Update(OrgCRUDL.Update):
        pass

    class List(OrgCRUDL.List):
        pass

    class Home(OrgCRUDL.Home):
        fields = ('name', 'timezone', 'api_token', 'contact_fields', 'last_label_task')
        field_config = {'api_token': {'label': _("RapidPro API Token")}}
        permission = 'orgs.org_home'

        def derive_title(self):
            return _("My Organization")

        def get_contact_fields(self, obj):
            return ', '.join(obj.get_contact_fields())

        def get_last_label_task(self, obj):
            result = obj.get_task_result(TaskType.label_messages)
            if result:
                when = format_datetime(ms_to_datetime(result['time']))
                stats = result['counts']
                return "%s (%d new messages, %d new labels)" % (when, stats['messages'], stats['labels'])
            else:
                return None

    class Edit(InferOrgMixin, OrgPermsMixin, SmartUpdateView):
        class OrgExtForm(forms.ModelForm):
            name = forms.CharField(label=_("Organization"),
                                   help_text=_("The name of this organization"))

            timezone = TimeZoneField(help_text=_("The timezone your organization is in"))

            contact_fields = forms.MultipleChoiceField(choices=(), label=_("Contact fields"),
                                                       help_text=_("Contact fields to display"), required=False)

            banner_text = forms.CharField(label=_("Banner text"), widget=forms.Textarea,
                                          help_text=_("Banner text displayed to all users"), required=False)

            def __init__(self, *args, **kwargs):
                org = kwargs.pop('org')
                super(OrgExtCRUDL.Edit.OrgExtForm, self).__init__(*args, **kwargs)

                field_choices = []
                for field in org.get_temba_client().get_fields():
                    field_choices.append((field.key, "%s (%s)" % (field.label, field.key)))

                self.fields['contact_fields'].choices = field_choices
                self.fields['contact_fields'].initial = org.get_contact_fields()

                self.fields['banner_text'].initial = org.get_banner_text()

            class Meta:
                model = Org
                fields = ('name', 'timezone', 'contact_fields', 'banner_text', 'logo')

        permission = 'orgs.org_edit'
        title = _("Edit My Organization")
        success_url = '@orgs_ext.org_home'
        form_class = OrgExtForm

        def get_form_kwargs(self):
            kwargs = super(OrgExtCRUDL.Edit, self).get_form_kwargs()
            kwargs['org'] = self.request.user.get_org()
            return kwargs

        def pre_save(self, obj):
            obj = super(OrgExtCRUDL.Edit, self).pre_save(obj)
            obj.set_contact_fields(self.form.cleaned_data['contact_fields'])
            obj.set_banner_text(self.form.cleaned_data['banner_text'])
            return obj

    class Chooser(OrgCRUDL.Chooser):
        pass

    class Choose(OrgCRUDL.Choose):
        pass
