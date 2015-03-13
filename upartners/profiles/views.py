from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.validators import MinLengthValidator
from django.db.models import Q
from django.http import Http404
from smartmin.users.views import SmartCRUDL, SmartCreateView, SmartListView, SmartReadView, SmartUpdateView


class UserForm(forms.ModelForm):
    """
    Form for user profiles
    """
    full_name = forms.CharField(max_length=128, label=_("Full name"))

    is_active = forms.BooleanField(label=_("Active"), required=False,
                                   help_text=_("Whether this user is active, disable to remove access."))

    email = forms.CharField(max_length=256,
                            label=_("Email"), help_text=_("Email address and login."))

    password = forms.CharField(widget=forms.PasswordInput, validators=[MinLengthValidator(8)],
                               label=_("Password"), help_text=_("Password used to log in (minimum of 8 characters)."))

    new_password = forms.CharField(widget=forms.PasswordInput, validators=[MinLengthValidator(8)], required=False,
                                   label=_("New password"),
                                   help_text=_("Password used to login (minimum of 8 characters, optional)."))

    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False, label=_("Confirm password"))

    change_password = forms.BooleanField(label=_("Require change"), required=False,
                                         help_text=_("Whether user must change password on next login."))

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')

        super(UserForm, self).__init__(*args, **kwargs)

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
        kwargs['user'] = self.request.user
        return kwargs

    def derive_initial(self):
        initial = super(UserFormMixin, self).derive_initial()
        if self.object:
            initial['full_name'] = self.object.profile.full_name
        return initial

    def post_save(self, obj):
        obj = super(UserFormMixin, self).post_save(obj)
        data = self.form.cleaned_data
        obj.profile.full_name = data['full_name']
        obj.profile.save()

        password = data.get('new_password', None) or data.get('password', None)
        if password:
            obj.set_password(password)
            obj.save()

        return obj


class UserFieldsMixin(object):
    def get_full_name(self, obj):
        return obj.profile.full_name


class UserCRUDL(SmartCRUDL):
    model = User
    actions = ('create', 'update', 'read', 'self', 'list')

    class Create(OrgPermsMixin, UserFormMixin, SmartCreateView):
        fields = ('full_name', 'email', 'password', 'confirm_password', 'change_password', 'regions')
        form_class = UserForm
        permission = 'profiles.profile_user_create'
        success_message = _("New supervisor created")
        title = _("Create Supervisor")

        def save(self, obj):
            org = self.request.user.get_org()
            full_name = self.form.cleaned_data['full_name']
            password = self.form.cleaned_data['password']
            change_password = self.form.cleaned_data['change_password']
            self.object = User.create(org, full_name, obj.email, password, change_password)

    class Update(OrgPermsMixin, UserFormMixin, SmartUpdateView):
        fields = ('full_name', 'email', 'new_password', 'confirm_password', 'regions', 'is_active')
        form_class = UserForm
        permission = 'profiles.profile_user_update'
        success_message = _("Supervisor updated")
        title = _("Edit Supervisor")

        def derive_initial(self):
            initial = super(UserCRUDL.Update, self).derive_initial()
            initial['regions'] = self.object.regions.all()
            return initial

    class Self(OrgPermsMixin, UserFormMixin, SmartUpdateView):
        """
        Limited update form for users to edit their own profiles
        """
        form_class = UserForm
        success_url = '@home.home'
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
        fields = ('full_name', 'type', 'email')
        permission = 'profiles.profile_user_read'

        def derive_title(self):
            if self.object == self.request.user:
                return _("My Profile")
            else:
                return super(UserCRUDL.Read, self).derive_title()

        def get_queryset(self):
            queryset = super(UserCRUDL.Read, self).get_queryset()

            # only allow access to active users attached to this org
            org = self.request.org
            return queryset.filter(Q(org_editors=org) | Q(org_admins=org)).filter(is_active=True)

        def get_context_data(self, **kwargs):
            context = super(UserCRUDL.Read, self).get_context_data(**kwargs)
            edit_button_url = None

            if self.object == self.request.user:
                edit_button_url = reverse('profiles.user_self')
            elif self.has_org_perm('profiles.profile_user_update'):
                edit_button_url = reverse('profiles.user_update', args=[self.object.pk])

            context['edit_button_url'] = edit_button_url
            return context

        def get_type(self, obj):
            if obj.is_admin_for(self.request.org):
                return _("Administrator")
            else:
                return _("Supervisor")

    class List(OrgPermsMixin, UserFieldsMixin, SmartListView):
        default_order = ('profile__full_name',)
        fields = ('full_name', 'email', 'regions')
        permission = 'profiles.profile_user_list'
        select_related = ('profile',)
        title = _("Supervisors")

        def derive_queryset(self, **kwargs):
            qs = super(UserCRUDL.List, self).derive_queryset(**kwargs)
            qs = qs.filter(pk__in=self.request.org.get_org_editors(), is_active=True)
            return qs


class ManageUserCRUDL(SmartCRUDL):
    """
    CRUDL used only by superusers to manage users outside the context of an organization
    """
    model = User
    model_name = 'Admin'
    path = 'admin'
    actions = ('create', 'update', 'list')

    class Create(OrgPermsMixin, UserFormMixin, SmartCreateView):
        fields = ('full_name', 'email', 'password', 'confirm_password', 'change_password')
        form_class = UserForm

        def save(self, obj):
            full_name = self.form.cleaned_data['full_name']
            password = self.form.cleaned_data['password']
            change_password = self.form.cleaned_data['change_password']
            self.object = User.create(None, full_name, obj.email, password, change_password)

    class Update(OrgPermsMixin, UserFormMixin, SmartUpdateView):
        fields = ('full_name', 'email', 'new_password', 'confirm_password', 'is_active')
        form_class = UserForm

    class List(UserFieldsMixin, SmartListView):
        fields = ('full_name', 'email', 'orgs')
        default_order = ('profile__full_name',)
        select_related = ('profile', 'org_admins', 'org_editors')

        def derive_queryset(self, **kwargs):
            qs = super(ManageUserCRUDL.List, self).derive_queryset(**kwargs)
            qs = qs.filter(is_active=True).exclude(profile=None)
            return qs

        def get_orgs(self, obj):
            orgs = set(obj.org_admins.all()) | set(obj.org_editors.all())
            return ", ".join([unicode(o) for o in orgs])

        def lookup_field_link(self, context, field, obj):
            return reverse('profiles.admin_update', args=[obj.pk])