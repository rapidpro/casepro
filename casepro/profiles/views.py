from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.validators import MinLengthValidator
from django.db.models import Q
from django.http import Http404, HttpResponse
from smartmin.users.views import SmartCreateView, SmartListView, SmartDeleteView, SmartReadView, SmartUpdateView
from smartmin.users.views import SmartCRUDL
from casepro.cases.models import Partner
from casepro.profiles import ROLE_ANALYST, ROLE_MANAGER, ROLE_CHOICES


class UserForm(forms.ModelForm):
    """
    Form for user profiles
    """
    full_name = forms.CharField(label=_("Full name"), max_length=128)

    partner = forms.ModelChoiceField(label=_("Partner Organization"), queryset=Partner.objects.none())

    role = forms.ChoiceField(label=_("Role"), choices=ROLE_CHOICES, required=True, initial=ROLE_ANALYST)

    email = forms.CharField(label=_("Email"), max_length=256,
                            help_text=_("Email address and login."))

    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput, validators=[MinLengthValidator(8)],
                               help_text=_("Password used to log in (minimum of 8 characters)."))

    new_password = forms.CharField(widget=forms.PasswordInput, validators=[MinLengthValidator(8)], required=False,
                                   label=_("New password"),
                                   help_text=_("Password used to login (minimum of 8 characters, optional)."))

    confirm_password = forms.CharField(label=_("Confirm password"), widget=forms.PasswordInput, required=False)

    change_password = forms.BooleanField(label=_("Require change"), required=False,
                                         help_text=_("Whether user must change password on next login."))

    def __init__(self, *args, **kwargs):
        self.org = kwargs.pop('org')

        super(UserForm, self).__init__(*args, **kwargs)

        self.fields['partner'].queryset = Partner.get_all(self.org)

    def clean(self):
        cleaned_data = super(UserForm, self).clean()

        password = cleaned_data.get('password', None) or cleaned_data.get('new_password', None)
        if password:
            confirm_password = cleaned_data.get('confirm_password', '')
            if password != confirm_password:
                self.add_error('confirm_password', _("Passwords don't match."))

    class Meta:
        model = User
        exclude = ()


class UserFormMixin(object):
    """
    Mixin for views that use a user form
    """
    def get_form_kwargs(self):
        kwargs = super(UserFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.org
        return kwargs

    def derive_initial(self):
        initial = super(UserFormMixin, self).derive_initial()
        if self.object:
            is_manager = self.object in self.request.org.get_org_editors()

            initial['full_name'] = self.object.profile.full_name
            initial['partner'] = self.object.profile.partner
            initial['role'] = ROLE_MANAGER if is_manager else ROLE_ANALYST
        return initial

    def post_save(self, obj):
        obj = super(UserFormMixin, self).post_save(obj)
        user = self.request.user
        data = self.form.cleaned_data

        obj.profile.full_name = data['full_name']

        if 'partner' in data and user.is_admin_for(self.request.org):  # only admins can update a user's partner
            obj.profile.partner = data['partner']

        obj.profile.save()

        if 'role' in data:
            obj.update_role(self.request.org, data['role'])

        password = data.get('new_password', None) or data.get('password', None)
        if password:
            obj.set_password(password)
            obj.save()

        return obj


class UserFieldsMixin(object):
    def get_full_name(self, obj):
        return obj.profile.full_name

    def get_partner(self, obj):
        partner = obj.get_partner()
        return partner if partner else ''


class UserCRUDL(SmartCRUDL):
    model = User
    actions = ('create', 'update', 'read', 'self', 'delete', 'list')

    class Create(OrgPermsMixin, UserFormMixin, SmartCreateView):
        form_class = UserForm
        permission = 'profiles.profile_user_create'

        def has_permission(self, request, *args, **kwargs):
            org = self.request.org

            # non-admins can't access this view without a specified partner
            if org and 'partner_id' not in self.kwargs and not self.request.user.is_admin_for(org):
                return False

            return super(UserCRUDL.Create, self).has_permission(request, *args, **kwargs)

        def derive_fields(self):
            fields = ['full_name']
            if self.request.org:
                if 'partner_id' not in self.kwargs:
                    fields.append('partner')
                fields.append('role')
            return fields + ['email', 'password', 'confirm_password', 'change_password']

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.org

            if 'partner_id' in self.kwargs:
                partner = Partner.get_all(org).get(pk=self.kwargs['partner_id'])
            else:
                partner = data.get('partner', None)

            full_name = data['full_name']
            role = data.get('role', None)
            password = data['password']
            change_password = data['change_password']
            self.object = User.create(org, partner, role, full_name, obj.email, password, change_password)

        def post_save(self, obj):
            return obj

        def get_success_url(self):
            if 'partner_id' in self.kwargs:
                return reverse('cases.partner_read', args=[self.kwargs['partner_id']])
            else:
                return reverse('profiles.user_list')

    class Update(OrgPermsMixin, UserFormMixin, SmartUpdateView):
        form_class = UserForm

        def has_permission(self, request, *args, **kwargs):
            return request.user.can_edit(request.org, self.get_object())

        def derive_fields(self):
            fields = ['full_name']
            if self.request.org:
                if self.request.user.is_admin_for(self.request.org):
                    fields.append('partner')
                fields.append('role')
            return fields + ['email', 'new_password', 'confirm_password']

        def get_success_url(self):
            return reverse('profiles.user_read', args=[self.object.pk])

    class Self(OrgPermsMixin, UserFormMixin, SmartUpdateView):
        """
        Limited update form for users to edit their own profiles
        """
        form_class = UserForm
        success_url = '@cases.inbox'
        success_message = _("Profile updated")
        title = _("Edit My Profile")

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'^profile/self/$'

        def has_permission(self, request, *args, **kwargs):
            return self.request.user.is_authenticated()

        def get_object(self, queryset=None):
            if not self.request.user.has_profile():
                raise Http404(_("User doesn't have a profile"))

            return self.request.user

        def pre_save(self, obj):
            obj = super(UserCRUDL.Self, self).pre_save(obj)
            if 'password' in self.form.cleaned_data:
                self.object.profile.change_password = False

            return obj

        def derive_fields(self):
            fields = ['full_name', 'email']
            if self.object.profile.change_password:
                fields += ['password']
            else:
                fields += ['new_password']
            return fields + ['confirm_password']

    class Read(OrgPermsMixin, UserFieldsMixin, SmartReadView):
        permission = 'profiles.profile_user_read'

        def derive_title(self):
            if self.object == self.request.user:
                return _("My Profile")
            else:
                return super(UserCRUDL.Read, self).derive_title()

        def derive_fields(self):
            fields = ['full_name', 'email']
            if self.object.profile.partner:
                fields += ['partner']
            return fields + ['role']

        def get_queryset(self):
            queryset = super(UserCRUDL.Read, self).get_queryset()

            # only allow access to active users attached to this org
            org = self.request.org
            return queryset.filter(Q(org_admins=org) | Q(org_editors=org) | Q(org_viewers=org)).filter(is_active=True)

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

            context['edit_button_url'] = edit_button_url
            context['can_delete'] = can_delete
            return context

        def get_role(self, obj):
            org = self.request.org
            if obj.is_admin_for(org):
                return _("Administrator")
            elif org.editors.filter(pk=obj.pk).exists():
                return _("Manager")
            elif org.viewers.filter(pk=obj.pk).exists():
                return _("Data Analyst")
            else:
                return None

    class Delete(OrgPermsMixin, SmartDeleteView):
        cancel_url = '@profiles.user_list'

        def has_permission(self, request, *args, **kwargs):
            return request.user.can_edit(request.org, self.get_object())

        def post(self, request, *args, **kwargs):
            user = self.get_object()
            user.release()
            return HttpResponse(status=204)

    class List(OrgPermsMixin, UserFieldsMixin, SmartListView):
        default_order = ('profile__full_name',)
        fields = ('full_name', 'email', 'partner')
        link_fields = ('full_name', 'partner')
        permission = 'profiles.profile_user_list'
        select_related = ('profile',)

        def derive_queryset(self, **kwargs):
            qs = super(UserCRUDL.List, self).derive_queryset(**kwargs)
            org = self.request.org
            if org:
                qs = qs.filter(Q(pk__in=org.get_org_admins()) | Q(pk__in=org.get_org_editors()) | Q(pk__in=org.get_org_viewers()))
            qs = qs.filter(is_active=True, pk__gt=1)
            return qs

        def lookup_field_link(self, context, field, obj):
            if field == 'partner':
                partner = obj.get_partner()
                return reverse('cases.partner_read', args=[partner.pk]) if partner else None
            else:
                return super(UserCRUDL.List, self).lookup_field_link(context, field, obj)
