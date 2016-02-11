from __future__ import unicode_literals

from dash.orgs.views import OrgPermsMixin
from django import forms
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartCRUDL, SmartListView, SmartFormView
from .models import Contact, Group, Field


class ContactCRUDL(SmartCRUDL):
    model = Contact
    actions = ('list',)

    class List(OrgPermsMixin, SmartListView):
        fields = ('uuid', 'name', 'language', 'created_on')

        def get_queryset(self, **kwargs):
            return self.model.objects.filter(org=self.request.org)


class GroupCRUDL(SmartCRUDL):
    model = Group
    actions = ('list', 'select')

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'contacts')
        default_order = ('name',)

        def derive_queryset(self, **kwargs):
            return Group.get_all(self.request.org, visible=True)

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
        fields = ('key', 'label', 'value_type')

        def get_queryset(self, **kwargs):
            return self.model.objects.filter(org=self.request.org)
