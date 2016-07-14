from __future__ import unicode_literals

from dash.orgs.views import OrgObjPermsMixin, OrgPermsMixin
from django import forms
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartCRUDL, SmartReadView, SmartListView, SmartFormView

from casepro.utils import JSONEncoder

from .models import Contact, Group, Field


class ContactCRUDL(SmartCRUDL):
    """
    Simple contact CRUDL for debugging by superusers, i.e. not exposed to regular users for now
    """
    model = Contact
    actions = ('list', 'read', 'fetch')

    class List(OrgPermsMixin, SmartListView):
        fields = ('uuid', 'name', 'language', 'created_on')

        def get_queryset(self, **kwargs):
            return self.model.objects.filter(org=self.request.org)

    class Read(OrgObjPermsMixin, SmartReadView):
        base_fields = ['language', 'groups']
        superuser_fields = ['uuid', 'created_on', 'is_blocked', 'is_active']

        def get_queryset(self, **kwargs):
            contact_fields = Field.get_all(self.request.org, visible=True)
            self.contact_field_keys = [f.key for f in contact_fields]
            self.contact_field_labels = {f.key: f.label for f in contact_fields}

            return self.model.objects.filter(org=self.request.org)

        def derive_fields(self):
            fields = self.base_fields + self.contact_field_keys

            if self.request.user.is_superuser:
                fields += self.superuser_fields

            return fields

        def get_groups(self, obj):
            return ", ".join([g.name for g in obj.groups.all()])

        def lookup_field_value(self, context, obj, field):
            if field in self.base_fields or field in self.superuser_fields:
                return super(ContactCRUDL.Read, self).lookup_field_value(context, obj, field)
            else:
                return obj.get_fields().get(field)

        def lookup_field_label(self, context, field, default=None):
            if field in self.base_fields or field in self.superuser_fields:
                return super(ContactCRUDL.Read, self).lookup_field_label(context, field, default)
            else:
                return self.contact_field_labels.get(field, default)

        def get_context_data(self, **kwargs):
            context = super(ContactCRUDL.Read, self).get_context_data(**kwargs)
            context['backend_url'] = settings.SITE_EXTERNAL_CONTACT_URL % self.object.uuid
            return context

    class Fetch(OrgObjPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching a single contact
        """
        permission = 'contacts.contact_read'

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse(self.object.as_json(full=True), encoder=JSONEncoder)


class GroupCRUDL(SmartCRUDL):
    model = Group
    actions = ('list', 'select')

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'contacts')
        default_order = 'name'

        def get_queryset(self, **kwargs):
            queryset = super(GroupCRUDL.List, self).get_queryset(**kwargs)
            return queryset.filter(org=self.request.org, is_visible=True)

        def get_contacts(self, obj):
            return obj.count if obj.count is not None else "..."

    class Select(OrgPermsMixin, SmartFormView):
        class GroupsForm(forms.Form):
            groups = forms.MultipleChoiceField(choices=(), label=_("Groups"),
                                               help_text=_("Contact groups visible to partner users."))

            def __init__(self, *args, **kwargs):
                org = kwargs['org']
                del kwargs['org']
                super(GroupCRUDL.Select.GroupsForm, self).__init__(*args, **kwargs)

                choices = [(group.pk, group.name) for group in Group.get_all(org).order_by('name')]

                self.fields['groups'].choices = choices
                self.fields['groups'].initial = [group.pk for group in Group.get_all(org, visible=True)]

        title = _("Contact Groups")
        form_class = GroupsForm
        success_url = '@contacts.group_list'
        submit_button_name = _("Update")
        success_message = _("Updated contact groups visible to partner users")

        def get_form_kwargs(self):
            kwargs = super(GroupCRUDL.Select, self).get_form_kwargs()
            kwargs['org'] = self.request.user.get_org()
            return kwargs

        def form_valid(self, form):
            selected_ids = form.cleaned_data['groups']
            org_groups = Group.objects.filter(org=self.request.org)

            org_groups.filter(pk__in=selected_ids).update(is_visible=True)
            org_groups.exclude(pk__in=selected_ids).update(is_visible=False)

            return HttpResponseRedirect(self.get_success_url())


class FieldCRUDL(SmartCRUDL):
    model = Field
    actions = ('list',)

    class List(OrgPermsMixin, SmartListView):
        """
        Basic list view mostly for debugging
        """
        fields = ('key', 'label', 'value_type', 'is_visible')
        default_order = 'key'

        def get_queryset(self, **kwargs):
            queryset = super(FieldCRUDL.List, self).get_queryset(**kwargs)
            return queryset.filter(org=self.request.org)
