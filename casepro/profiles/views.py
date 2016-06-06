from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponse
from smartmin.views import SmartCreateView, SmartDeleteView, SmartReadView, SmartUpdateView
from smartmin.views import SmartListView, SmartCRUDL

from casepro.cases.mixins import PartnerPermsMixin
from casepro.cases.models import Partner
from casepro.orgs_ext.mixins import OrgFormMixin
from casepro.utils import json_encode

from .forms import UserForm, OrgUserForm, PartnerUserForm
from .models import Profile


class UserFieldsMixin(object):
    def get_name(self, obj):
        return obj.profile.full_name

    def get_partner(self, obj):
        partner = obj.get_partner(self.request.org)
        return partner if partner else ''


class UserUpdateMixin(OrgFormMixin):
    """
    Mixin for views that update user
    """
    def derive_initial(self):
        initial = super(UserUpdateMixin, self).derive_initial()
        initial['name'] = self.object.profile.full_name
        initial['role'] = self.object.profile.get_role(self.request.org)
        initial['partner'] = self.object.profile.partner
        return initial

    def post_save(self, obj):
        obj = super(UserUpdateMixin, self).post_save(obj)
        data = self.form.cleaned_data

        obj.profile.full_name = data['name']
        obj.profile.save(update_fields=('full_name',))

        if 'role' in data:
            role = data['role']
            partner = data['partner'] if 'partner' in data else self.get_partner(self.request.org)
            obj.profile.update_role(self.request.org, role, partner)

        # set new password if provided
        password = data['new_password']
        if password:
            obj.set_password(password)
            obj.save()

        return obj


class UserCRUDL(SmartCRUDL):
    model = User
    actions = ('create', 'create_in', 'update', 'read', 'self', 'delete', 'list')

    class Create(OrgPermsMixin, OrgFormMixin, SmartCreateView):
        """
        Form used by org admins to create any kind of user, and used by superusers to create unattached users
        """
        permission = 'profiles.profile_user_create'
        success_url = '@profiles.user_list'

        def get_form_class(self):
            return OrgUserForm if self.request.org else UserForm

        def derive_fields(self):
            if self.request.org:
                return 'name', 'role', 'partner', 'email', 'password', 'confirm_password', 'change_password'
            else:
                return 'name', 'email', 'password', 'confirm_password', 'change_password'

        def save(self, obj):
            org = self.request.org
            name = self.form.cleaned_data['name']
            email = self.form.cleaned_data['email']
            password = self.form.cleaned_data['password']
            change_password = self.form.cleaned_data['change_password']

            if org:
                role = self.form.cleaned_data['role']
                partner = self.form.cleaned_data['partner']

                if partner:
                    self.object = Profile.create_partner_user(org, partner, role, name, email,
                                                              password, change_password)
                else:
                    self.object = Profile.create_org_user(org, name, email, password, change_password)
            else:
                self.object = Profile.create_user(name, email, password, change_password)

    class CreateIn(PartnerPermsMixin, OrgFormMixin, SmartCreateView):
        """
        Form for creating partner-level users in a specific partner
        """
        permission = 'profiles.profile_user_create_in'
        form_class = PartnerUserForm
        fields = ('name', 'role', 'email', 'password', 'confirm_password', 'change_password')

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'^user/create_in/(?P<partner_id>\d+)/$'

        def get_partner(self):
            return Partner.get_all(self.request.org).get(pk=self.kwargs['partner_id'])

        def save(self, obj):
            org = self.request.org
            partner = self.get_partner()
            role = self.form.cleaned_data['role']
            name = self.form.cleaned_data['name']
            email = self.form.cleaned_data['email']
            password = self.form.cleaned_data['password']
            change_password = self.form.cleaned_data['change_password']

            self.object = Profile.create_partner_user(org, partner, role, name, email, password, change_password)

        def get_success_url(self):
            return reverse('cases.partner_read', args=[self.kwargs['partner_id']])

    class Update(PartnerPermsMixin, UserUpdateMixin, SmartUpdateView):
        """
        Form for updating any kind of user by another user
        """
        permission = 'profiles.profile_user_update'
        form_class = UserForm

        def get_form_class(self):
            if self.request.org:
                if self.request.user.get_partner(self.request.org):
                    return PartnerUserForm
                else:
                    return OrgUserForm
            else:
                return UserForm

        def get_queryset(self):
            if self.request.org:
                return self.request.org.get_users()
            else:
                return super(UserCRUDL.Update, self).get_queryset()

        def get_partner(self):
            return self.get_object().get_partner(self.request.org)

        def derive_fields(self):
            profile_fields = ['name']
            user_fields = ['email', 'new_password', 'confirm_password', 'change_password']

            if self.request.org:
                user_partner = self.request.user.get_partner(self.request.org)
                if user_partner:
                    profile_fields += ['role']  # partner users can't change a user's partner
                else:
                    profile_fields += ['role', 'partner']

            return profile_fields + user_fields

        def get_success_url(self):
            return reverse('profiles.user_read', args=[self.object.pk])

    class Self(OrgPermsMixin, UserUpdateMixin, SmartUpdateView):
        """
        Limited update form for users to edit their own profiles
        """
        form_class = UserForm
        fields = ('name', 'email', 'new_password', 'confirm_password')
        success_url = '@cases.inbox'
        success_message = _("Profile updated")
        title = _("Edit My Profile")

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'^profile/self/$'

        def has_permission(self, request, *args, **kwargs):
            return self.request.user.is_authenticated()

        def get_form_kwargs(self):
            kwargs = super(UserCRUDL.Self, self).get_form_kwargs()
            kwargs['require_password_change'] = self.object.profile.change_password
            return kwargs

        def get_object(self, queryset=None):
            if not self.request.user.has_profile():
                raise Http404(_("User doesn't have a profile"))

            return self.request.user

        def post_save(self, obj):
            obj = super(UserCRUDL.Self, self).post_save(obj)
            obj.profile.change_password = False
            obj.profile.save(update_fields=('change_password',))
            return obj

    class Read(OrgPermsMixin, UserFieldsMixin, SmartReadView):
        permission = 'profiles.profile_user_read'

        def derive_title(self):
            if self.object == self.request.user:
                return _("My Profile")
            else:
                return super(UserCRUDL.Read, self).derive_title()

        def derive_fields(self):
            fields = ['name', 'email']
            if self.object.profile.partner:
                fields += ['partner']
            return fields + ['role']

        def get_queryset(self):
            if self.request.org:
                return self.request.org.get_users()
            else:
                return super(UserCRUDL.Read, self).get_queryset()

        def get_context_data(self, **kwargs):
            context = super(UserCRUDL.Read, self).get_context_data(**kwargs)
            org = self.request.org
            user = self.request.user

            if self.object == user:
                edit_button_url = reverse('profiles.user_self')
                can_delete = False  # can't delete yourself
            elif user.can_edit(org, self.object):
                edit_button_url = reverse('profiles.user_update', args=[self.object.pk])
                can_delete = True
            else:
                edit_button_url = None
                can_delete = False

            context['context_data_json'] = json_encode({'user': self.object.as_json()})
            context['edit_button_url'] = edit_button_url
            context['can_delete'] = can_delete
            return context

        def get_role(self, obj):
            org = self.request.org

            if obj.can_administer(org):
                return _("Administrator")
            elif org.editors.filter(pk=obj.pk).exists():
                return _("Manager")
            elif org.viewers.filter(pk=obj.pk).exists():
                return _("Data Analyst")

    class Delete(OrgPermsMixin, SmartDeleteView):
        cancel_url = '@profiles.user_list'

        def has_permission(self, request, *args, **kwargs):
            user = self.get_object()
            return request.user.can_edit(request.org, user) and request.user != user

        def get_queryset(self):
            return self.request.org.get_users()

        def post(self, request, *args, **kwargs):
            user = self.get_object()
            user.remove_from_org(request.org)

            return HttpResponse(status=204)

    class List(OrgPermsMixin, UserFieldsMixin, SmartListView):
        default_order = ('profile__full_name',)
        fields = ('name', 'email', 'partner')
        link_fields = ('name', 'partner')
        permission = 'profiles.profile_user_list'
        select_related = ('profile',)

        def derive_queryset(self, **kwargs):
            if self.request.org:
                return self.request.org.get_users().exclude(profile=None)
            else:
                return super(UserCRUDL.List, self).derive_queryset(**kwargs)

        def lookup_field_link(self, context, field, obj):
            if field == 'partner':
                partner = obj.get_partner(self.request.org)
                return reverse('cases.partner_read', args=[partner.pk]) if partner else None
            else:
                return super(UserCRUDL.List, self).lookup_field_link(context, field, obj)
