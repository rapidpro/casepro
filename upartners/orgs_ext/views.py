from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from dash.orgs.views import OrgCRUDL, OrgForm, InferOrgMixin, OrgPermsMixin, SmartUpdateView
from django.utils.translation import ugettext_lazy as _
from smartmin.users.views import SmartCRUDL


def org_ext_context_processor(request):
    is_admin = request.org and not request.user.is_anonymous() and request.user.is_admin_for(request.org)
    return dict(user_is_admin=is_admin)


class OrgExtCRUDL(SmartCRUDL):
    actions = ('create', 'update', 'list', 'home', 'edit', 'choose')
    model = Org

    class Create(OrgCRUDL.Create):
        pass

    class Update(OrgCRUDL.Update):
        pass

    class List(OrgCRUDL.List):
        pass

    class Home(OrgCRUDL.Home):
        fields = ('name', 'timezone', 'api_token')
        field_config = {'api_token': {'label': _("RapidPro API Token")}}
        permission = 'orgs.org_home'

        def derive_title(self):
            return _("My Organization")

    class Edit(InferOrgMixin, OrgPermsMixin, SmartUpdateView):
        fields = ('name', 'timezone')
        permission = 'orgs.org_edit'
        title = _("Edit My Organization")
        success_url = '@orgs_ext.org_home'
        form_class = OrgForm

    class Choose(OrgCRUDL.Choose):
        pass
