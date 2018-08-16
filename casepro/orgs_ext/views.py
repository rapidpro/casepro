from dash.orgs.models import Org
from dash.orgs.views import InferOrgMixin, OrgCRUDL, OrgPermsMixin, TaskCRUDL
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartCRUDL, SmartUpdateView

from casepro.cases.models import Case
from casepro.contacts.models import Field, Group
from casepro.statistics.models import DailyCount

from .forms import OrgEditForm, OrgForm


class OrgExtCRUDL(SmartCRUDL):
    actions = ("create", "update", "list", "home", "edit", "chooser", "choose")
    model = Org

    class Create(OrgCRUDL.Create):
        form_class = OrgForm
        fields = ("name", "language", "timezone", "subdomain", "logo", "administrators")

    class Update(OrgCRUDL.Update):
        form_class = OrgForm
        fields = ("name", "language", "timezone", "subdomain", "logo", "administrators", "is_active")

    class List(OrgCRUDL.List):
        default_order = ("name",)

    class Home(OrgCRUDL.Home):
        permission = "orgs.org_home"

        def get_context_data(self, **kwargs):
            context = super(OrgExtCRUDL.Home, self).get_context_data(**kwargs)
            context["summary"] = self.get_summary(self.request.org)
            return context

        def get_summary(self, org):
            return {
                "total_incoming": DailyCount.get_by_org([org], DailyCount.TYPE_INCOMING).total(),
                "total_replies": DailyCount.get_by_org([org], DailyCount.TYPE_REPLIES).total(),
                "cases_open": Case.objects.filter(org=org, closed_on=None).count(),
                "cases_closed": Case.objects.filter(org=org).exclude(closed_on=None).count(),
            }

    class Edit(InferOrgMixin, OrgPermsMixin, SmartUpdateView):
        permission = "orgs.org_edit"
        title = _("Edit My Organization")
        success_url = "@orgs_ext.org_home"
        form_class = OrgEditForm

        def get_form_kwargs(self):
            kwargs = super(OrgExtCRUDL.Edit, self).get_form_kwargs()
            kwargs["org"] = self.request.user.get_org()
            return kwargs

        def pre_save(self, obj):
            obj = super(OrgExtCRUDL.Edit, self).pre_save(obj)
            obj.set_banner_text(self.form.cleaned_data["banner_text"])

            field_ids = self.form.cleaned_data["contact_fields"]

            Field.get_all(self.request.org).filter(pk__in=field_ids).update(is_visible=True)
            Field.get_all(self.request.org).exclude(pk__in=field_ids).update(is_visible=False)

            group_ids = self.form.cleaned_data["suspend_groups"]

            Group.get_all(self.request.org).filter(pk__in=group_ids).update(suspend_from=True)
            Group.get_all(self.request.org).exclude(pk__in=group_ids).update(suspend_from=False)

            return obj

    class Chooser(OrgCRUDL.Chooser):
        pass

    class Choose(OrgCRUDL.Choose):
        pass


class TaskExtCRUDL(TaskCRUDL):
    class List(TaskCRUDL.List):
        link_fields = ("org",)

        def lookup_field_link(self, context, field, obj):
            return reverse("orgs_ext.org_update", args=[obj.org_id])
