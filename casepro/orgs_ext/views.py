from __future__ import unicode_literals

from dash.orgs.models import Org
from dash.orgs.views import OrgCRUDL, TaskCRUDL, InferOrgMixin, OrgPermsMixin
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartCRUDL, SmartUpdateView

from casepro.contacts.models import Field, Group

from .forms import OrgForm, OrgEditForm


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
        default_order = ('name',)

    class Home(OrgCRUDL.Home):
        fields = ('name', 'timezone', 'api_token', 'contact_fields', 'administrators')
        field_config = {'api_token': {'label': _("RapidPro API Token")}}
        permission = 'orgs.org_home'

        def derive_title(self):
            return _("My Organization")

        def get_contact_fields(self, obj):
            return ', '.join([f.key for f in Field.get_all(obj, visible=True)])

        def get_administrators(self, obj):
            admins = obj.administrators.exclude(profile=None).order_by('profile__full_name').select_related('profile')
            return '<br/>'.join([unicode(u) for u in admins])

    class Edit(InferOrgMixin, OrgPermsMixin, SmartUpdateView):
        permission = 'orgs.org_edit'
        title = _("Edit My Organization")
        success_url = '@orgs_ext.org_home'
        form_class = OrgEditForm

        def get_form_kwargs(self):
            kwargs = super(OrgExtCRUDL.Edit, self).get_form_kwargs()
            kwargs['org'] = self.request.user.get_org()
            return kwargs

        def pre_save(self, obj):
            obj = super(OrgExtCRUDL.Edit, self).pre_save(obj)
            obj.set_banner_text(self.form.cleaned_data['banner_text'])

            field_ids = self.form.cleaned_data['contact_fields']

            Field.get_all(self.request.org).filter(pk__in=field_ids).update(is_visible=True)
            Field.get_all(self.request.org).exclude(pk__in=field_ids).update(is_visible=False)

            group_ids = self.form.cleaned_data['suspend_groups']

            Group.get_all(self.request.org).filter(pk__in=group_ids).update(suspend_from=True)
            Group.get_all(self.request.org).exclude(pk__in=group_ids).update(suspend_from=False)

            return obj

    class Chooser(OrgCRUDL.Chooser):
        pass

    class Choose(OrgCRUDL.Choose):
        pass


class TaskExtCRUDL(TaskCRUDL):
    class List(TaskCRUDL.List):
        def lookup_field_link(self, context, field, obj):
            if field == 'org':
                return reverse('orgs_ext.org_update', args=[obj.org_id])
            else:
                return super(TaskCRUDL.List, self).lookup_field_link(context, field, obj)
