from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from dash.orgs.views import OrgCRUDL, InferOrgMixin, OrgPermsMixin, SmartUpdateView, SmartListView
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartCRUDL
from timezones.forms import TimeZoneField
from .models import TaskState


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


class OrgExtCRUDL(SmartCRUDL):
    actions = ('create', 'update', 'list', 'home', 'edit', 'chooser', 'choose')
    model = Org

    class Create(OrgCRUDL.Create):
        form_class = OrgForm
        fields = ('name', 'language', 'timezone', 'subdomain', 'api_token', 'logo', 'administrators')

    class Update(OrgCRUDL.Update):
        form_class = OrgForm
        fields = ('name', 'language', 'timezone', 'subdomain', 'api_token', 'logo', 'administrators', 'is_active')

    class List(OrgCRUDL.List):
        pass

    class Home(OrgCRUDL.Home):
        fields = ('name', 'timezone', 'api_token', 'contact_fields', 'administrators')
        field_config = {'api_token': {'label': _("RapidPro API Token")}}
        permission = 'orgs.org_home'

        def derive_title(self):
            return _("My Organization")

        def get_contact_fields(self, obj):
            return ', '.join(obj.get_contact_fields())

        def get_administrators(self, obj):
            admins = obj.administrators.exclude(profile=None).order_by('profile__full_name').select_related('profile')
            return '<br/>'.join([unicode(u) for u in admins])

    class Edit(InferOrgMixin, OrgPermsMixin, SmartUpdateView):
        class OrgExtForm(forms.ModelForm):
            name = forms.CharField(label=_("Organization"),
                                   help_text=_("The name of this organization"))

            timezone = TimeZoneField(help_text=_("The timezone your organization is in"))

            banner_text = forms.CharField(label=_("Banner text"), widget=forms.Textarea,
                                          help_text=_("Banner text displayed to all users"), required=False)

            contact_fields = forms.MultipleChoiceField(choices=(), label=_("Contact fields"),
                                                       help_text=_("Contact fields to display"), required=False)

            suspend_groups = forms.MultipleChoiceField(choices=(), label=_("Suspend groups"),
                                                       help_text=_("Groups to remove contacts from when creating cases"),
                                                       required=False)

            def __init__(self, *args, **kwargs):
                org = kwargs.pop('org')
                super(OrgExtCRUDL.Edit.OrgExtForm, self).__init__(*args, **kwargs)
                client = org.get_temba_client()

                self.fields['banner_text'].initial = org.get_banner_text()

                field_choices = []
                for field in sorted(client.get_fields(), key=lambda f: f.key.lower()):
                    field_choices.append((field.key, "%s (%s)" % (field.label, field.key)))

                self.fields['contact_fields'].choices = field_choices
                self.fields['contact_fields'].initial = org.get_contact_fields()

                group_choices = []
                for group in sorted(client.get_groups(), key=lambda g: g.name.lower()):
                    group_choices.append((group.uuid, "%s (%s)" % (group.name, group.size)))

                self.fields['suspend_groups'].choices = group_choices
                self.fields['suspend_groups'].initial = org.get_suspend_groups()

            class Meta:
                model = Org
                fields = ('name', 'timezone', 'banner_text', 'contact_fields', 'suspend_groups', 'logo')

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
            obj.set_banner_text(self.form.cleaned_data['banner_text'])
            obj.set_contact_fields(self.form.cleaned_data['contact_fields'])
            obj.set_suspend_groups(self.form.cleaned_data['suspend_groups'])
            return obj

    class Chooser(OrgCRUDL.Chooser):
        pass

    class Choose(OrgCRUDL.Choose):
        pass


class TaskCRUDL(SmartCRUDL):
    actions = ('list',)
    model = TaskState
    model_name = _("Task")
    path = 'task'

    class List(SmartListView):
        title = _("Tasks")
        link_fields = ('org',)
        default_order = ('org__name', 'task_key')

        def lookup_field_link(self, context, field, obj):
            if field == 'org':
                return reverse('orgs_ext.org_update', args=[obj.org_id])
            else:
                return super(TaskCRUDL.List, self).lookup_field_link(context, field, obj)
