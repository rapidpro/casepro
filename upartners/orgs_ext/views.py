from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from dash.orgs.views import OrgCRUDL, OrgForm, InferOrgMixin, OrgPermsMixin, SmartUpdateView
from django import forms
from django.utils.translation import ugettext_lazy as _
from smartmin.users.views import SmartCRUDL


def org_ext_context_processor(request):
    is_admin = request.org and not request.user.is_anonymous() and request.user.is_admin_for(request.org)
    return dict(user_is_admin=is_admin)


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
        fields = ('name', 'timezone', 'api_token', 'contact_fields')
        field_config = {'api_token': {'label': _("RapidPro API Token")}}
        permission = 'orgs.org_home'

        def derive_title(self):
            return _("My Organization")

        def get_contact_fields(self, obj):
            return ', '.join(obj.get_contact_fields())

    class Edit(InferOrgMixin, OrgPermsMixin, SmartUpdateView):
        class OrgExtForm(OrgForm):
            contact_fields = forms.MultipleChoiceField(choices=(), label=_("Contact fields"),
                                                       help_text=_("Contact fields to display"), required=False)

            def __init__(self, *args, **kwargs):
                org = kwargs.pop('org')
                super(OrgExtCRUDL.Edit.OrgExtForm, self).__init__(*args, **kwargs)

                field_choices = []
                for field in org.get_temba_client().get_fields():
                    field_choices.append((field.key, "%s (%s)" % (field.label, field.key)))

                self.fields['contact_fields'].choices = field_choices
                self.fields['contact_fields'].initial = org.get_contact_fields()

            class Meta:
                model = Org

        fields = ('name', 'timezone', 'contact_fields')
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
            return obj

    class Chooser(OrgCRUDL.Chooser):
        pass

    class Choose(OrgCRUDL.Choose):
        pass
