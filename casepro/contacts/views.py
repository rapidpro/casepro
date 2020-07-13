from dash.orgs.views import OrgObjPermsMixin, OrgPermsMixin
from smartmin.views import SmartCRUDL, SmartFormView, SmartListView, SmartReadView

from django import forms
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Case
from casepro.utils import JSONEncoder

from .models import Contact, Field, Group


class ContactCRUDL(SmartCRUDL):
    """
    Simple contact CRUDL for debugging by superusers, i.e. not exposed to regular users for now
    """

    model = Contact
    actions = ("list", "read", "fetch", "cases")

    class List(OrgPermsMixin, SmartListView):
        fields = ("uuid", "name", "language", "created_on")

        def get_queryset(self, **kwargs):
            return self.model.objects.filter(org=self.request.org)

    class Read(OrgObjPermsMixin, SmartReadView):
        def get_context_data(self, **kwargs):
            context = super(ContactCRUDL.Read, self).get_context_data(**kwargs)

            fields = Field.get_all(self.object.org, visible=True).order_by("label")

            context["context_data_json"] = {
                "contact": self.object.as_json(full=True),
                "fields": [f.as_json() for f in fields],
            }
            context["backend_url"] = settings.SITE_EXTERNAL_CONTACT_URL % self.object.uuid
            return context

    class Fetch(OrgObjPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching a single contact
        """

        permission = "contacts.contact_read"

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse(self.object.as_json(full=True), encoder=JSONEncoder)

    class Cases(OrgObjPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching a contact's cases
        """

        permission = "contacts.contact_read"

        def get_context_data(self, **kwargs):
            context = super(ContactCRUDL.Cases, self).get_context_data(**kwargs)

            cases = (
                Case.get_all(self.request.org, self.request.user).filter(contact=self.object).order_by("-opened_on")
            )
            cases = cases.prefetch_related("labels").select_related("contact", "assignee")

            context["object_list"] = cases
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({"results": [c.as_json() for c in context["object_list"]]}, encoder=JSONEncoder)


class GroupCRUDL(SmartCRUDL):
    model = Group
    actions = ("list", "select")

    class List(OrgPermsMixin, SmartListView):
        fields = ("name", "contacts")
        default_order = "name"

        def get_queryset(self, **kwargs):
            queryset = super(GroupCRUDL.List, self).get_queryset(**kwargs)
            return queryset.filter(org=self.request.org, is_visible=True)

        def get_contacts(self, obj):
            return obj.count if obj.count is not None else "..."

    class Select(OrgPermsMixin, SmartFormView):
        class GroupsForm(forms.Form):
            groups = forms.MultipleChoiceField(
                choices=(), label=_("Groups"), help_text=_("Contact groups visible to partner users.")
            )

            def __init__(self, *args, **kwargs):
                org = kwargs["org"]
                del kwargs["org"]
                super(GroupCRUDL.Select.GroupsForm, self).__init__(*args, **kwargs)

                choices = [(group.pk, group.name) for group in Group.get_all(org).order_by("name")]

                self.fields["groups"].choices = choices
                self.fields["groups"].initial = [group.pk for group in Group.get_all(org, visible=True)]

        title = _("Contact Groups")
        form_class = GroupsForm
        success_url = "@contacts.group_list"
        submit_button_name = _("Update")
        success_message = _("Updated contact groups visible to partner users")

        def get_form_kwargs(self):
            kwargs = super(GroupCRUDL.Select, self).get_form_kwargs()
            kwargs["org"] = self.request.user.get_org()
            return kwargs

        def form_valid(self, form):
            selected_ids = form.cleaned_data["groups"]
            org_groups = Group.objects.filter(org=self.request.org)

            org_groups.filter(pk__in=selected_ids).update(is_visible=True)
            org_groups.exclude(pk__in=selected_ids).update(is_visible=False)

            return HttpResponseRedirect(self.get_success_url())


class FieldCRUDL(SmartCRUDL):
    model = Field
    actions = ("list",)

    class List(OrgPermsMixin, SmartListView):
        """
        Basic list view mostly for debugging
        """

        fields = ("key", "label", "value_type", "is_visible")
        default_order = "key"

        def get_queryset(self, **kwargs):
            queryset = super(FieldCRUDL.List, self).get_queryset(**kwargs)
            return queryset.filter(org=self.request.org)
