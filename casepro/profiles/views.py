from dash.orgs.views import OrgPermsMixin
from smartmin.views import SmartCreateView, SmartCRUDL, SmartDeleteView, SmartListView, SmartReadView, SmartUpdateView

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from casepro.cases.mixins import PartnerPermsMixin
from casepro.cases.models import Partner
from casepro.orgs_ext.mixins import OrgFormMixin
from casepro.statistics.models import DailyCount
from casepro.utils import month_range, str_to_bool

from .forms import OrgUserForm, PartnerUserForm, UserForm
from .models import Profile


class UserUpdateMixin(OrgFormMixin):
    """
    Mixin for views that update user
    """

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.get_user()
        return kwargs

    def derive_initial(self):
        initial = super().derive_initial()
        initial["name"] = self.object.profile.full_name
        if self.request.org:
            initial["role"] = self.object.get_role(self.request.org)
            initial["partner"] = self.object.get_partner(self.request.org)
        return initial

    def post_save(self, obj):
        obj = super().post_save(obj)
        data = self.form.cleaned_data

        obj.profile.full_name = data["name"]
        obj.profile.change_password = data.get("change_password", False)
        obj.profile.must_use_faq = data.get("must_use_faq", False)
        obj.profile.save(update_fields=("full_name", "change_password", "must_use_faq"))

        if "role" in data:
            role = data["role"]
            partner = data["partner"] if "partner" in data else self.get_partner()
            obj.update_role(self.request.org, role, partner)

        # set new password if provided
        password = data["new_password"]
        if password:
            obj.set_password(password)
            obj.save()
            update_session_auth_hash(self.request, obj)

        return obj


class UserCRUDL(SmartCRUDL):
    model = User
    actions = ("create", "create_in", "update", "read", "self", "delete", "list")

    class Create(OrgPermsMixin, OrgFormMixin, SmartCreateView):
        """
        Form used by org admins to create any kind of user, and used by superusers to create unattached users
        """

        permission = "profiles.profile_user_create"
        success_url = "@profiles.user_list"

        def get_form_class(self):
            return OrgUserForm if self.request.org else UserForm

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["user"] = self.get_user()
            return kwargs

        def derive_fields(self):
            if self.request.org:
                return (
                    "name",
                    "role",
                    "partner",
                    "email",
                    "password",
                    "confirm_password",
                    "change_password",
                    "must_use_faq",
                )
            else:
                return "name", "email", "password", "confirm_password", "change_password", "must_use_faq"

        def save(self, obj):
            org = self.request.org
            name = self.form.cleaned_data["name"]
            email = self.form.cleaned_data["email"]
            password = self.form.cleaned_data["password"]
            change_password = self.form.cleaned_data["change_password"]
            must_use_faq = self.form.cleaned_data["must_use_faq"]

            if org:
                role = self.form.cleaned_data["role"]
                partner = self.form.cleaned_data["partner"]

                if partner:
                    self.object = Profile.create_partner_user(
                        org, partner, role, name, email, password, change_password, must_use_faq
                    )
                else:
                    self.object = Profile.create_org_user(org, name, email, password, change_password, must_use_faq)
            else:
                self.object = Profile.create_user(name, email, password, change_password, must_use_faq)

        def get_success_url(self):
            return reverse("profiles.user_read", args=[self.object.pk])

    class CreateIn(PartnerPermsMixin, OrgFormMixin, SmartCreateView):
        """
        Form for creating partner-level users in a specific partner
        """

        permission = "profiles.profile_user_create_in"
        form_class = PartnerUserForm
        fields = ("name", "role", "email", "password", "confirm_password", "change_password", "must_use_faq")

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r"^user/create_in/(?P<partner_id>\d+)/$"

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["user"] = self.get_user()
            return kwargs

        def get_partner(self):
            return Partner.get_all(self.request.org).get(pk=self.kwargs["partner_id"])

        def save(self, obj):
            org = self.request.org
            partner = self.get_partner()
            role = self.form.cleaned_data["role"]
            name = self.form.cleaned_data["name"]
            email = self.form.cleaned_data["email"]
            password = self.form.cleaned_data["password"]
            change_password = self.form.cleaned_data["change_password"]
            must_use_faq = self.form.cleaned_data["must_use_faq"]

            self.object = Profile.create_partner_user(
                org, partner, role, name, email, password, change_password, must_use_faq
            )

        def get_success_url(self):
            return reverse("profiles.user_read", args=[self.object.pk])

    class Update(PartnerPermsMixin, UserUpdateMixin, SmartUpdateView):
        """
        Form for updating any kind of user by another user
        """

        permission = "profiles.profile_user_update"
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
                return super().get_queryset()

        def get_partner(self):
            return self.get_object().get_partner(self.request.org)

        def derive_fields(self):
            profile_fields = ["name"]
            user_fields = ["email", "new_password", "confirm_password", "change_password", "must_use_faq"]

            if self.request.org:
                user_partner = self.request.user.get_partner(self.request.org)
                if user_partner:
                    profile_fields += ["role"]  # partner users can't change a user's partner
                else:
                    profile_fields += ["role", "partner"]

            return tuple(profile_fields + user_fields)

        def get_success_url(self):
            return reverse("profiles.user_read", args=[self.object.pk])

    class Self(OrgPermsMixin, UserUpdateMixin, SmartUpdateView):
        """
        Limited update form for users to edit their own profiles
        """

        form_class = UserForm
        fields = ("name", "email", "current_password", "new_password", "confirm_password")
        success_url = "@cases.inbox"
        success_message = _("Profile updated")
        title = _("Edit My Profile")

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r"^profile/self/$"

        def has_permission(self, request, *args, **kwargs):
            return self.request.user.is_authenticated

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["user"] = self.get_user()
            kwargs["require_password_change"] = self.object.profile.change_password
            return kwargs

        def get_object(self, queryset=None):
            if not self.request.user.has_profile():
                raise Http404(_("User doesn't have a profile"))

            return self.request.user

        def post_save(self, obj):
            obj = super().post_save(obj)
            obj.profile.change_password = False
            obj.profile.save(update_fields=("change_password",))
            return obj

    class Read(OrgPermsMixin, SmartReadView):
        permission = "profiles.profile_user_read"

        def derive_title(self):
            if self.object == self.request.user:
                return _("My Profile")
            else:
                return super().derive_title()

        def derive_fields(self):
            profile_fields = ["name"]
            user_fields = ["email"]
            if self.request.org:
                user_partner = self.request.user.get_partner(self.request.org)
                if user_partner:
                    profile_fields += ["role"]  # partner users can't change a user's partner
                else:
                    profile_fields += ["role", "partner"]

            return tuple(profile_fields + user_fields)

        def get_queryset(self):
            if self.request.org:
                user_partner = self.request.user.get_partner(self.request.org)
                if user_partner:
                    return user_partner.get_users()
                return self.request.org.get_users()
            else:
                return super().get_queryset()

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            org = self.request.org
            user = self.request.user

            if self.object == user:
                edit_button_url = reverse("profiles.user_self")
                can_delete = False  # can't delete yourself
            elif user.can_edit(org, self.object):
                edit_button_url = reverse("profiles.user_update", args=[self.object.pk])
                can_delete = bool(org)  # can only delete in context of an org
            else:
                edit_button_url = None
                can_delete = False

            context["context_data_json"] = {"user": self.object.as_json(full=True, org=org)}
            context["edit_button_url"] = edit_button_url
            context["can_delete"] = can_delete
            context["summary"] = self.get_summary(org, self.object) if org else {}
            return context

        def get_summary(self, org, user):
            return {"total_replies": DailyCount.get_by_user(org, [user], DailyCount.TYPE_REPLIES, None, None).total()}

    class Delete(OrgPermsMixin, SmartDeleteView):
        cancel_url = "@profiles.user_list"

        def has_permission(self, request, *args, **kwargs):
            user = self.get_object()
            return request.user.can_edit(request.org, user) and request.user != user

        def get_queryset(self):
            return self.request.org.get_users()

        def post(self, request, *args, **kwargs):
            user = self.get_object()
            user.remove_from_org(request.org)

            return HttpResponse(status=204)

    class List(OrgPermsMixin, SmartListView):
        """
        JSON endpoint to fetch users with their activity information
        """

        permission = "profiles.profile_user_list"

        def get(self, request, *args, **kwargs):
            org = request.org
            partner_id = request.GET.get("partner")
            non_partner = str_to_bool(self.request.GET.get("non_partner", ""))
            with_activity = str_to_bool(self.request.GET.get("with_activity", ""))

            if non_partner:
                users = org.administrators.all()
            elif partner_id:
                users = Partner.objects.get(org=org, pk=partner_id).get_users()
            else:
                users = org.get_users()

            users = list(users.order_by("profile__full_name"))

            # get reply statistics
            if with_activity:
                replies_total = DailyCount.get_by_user(org, users, DailyCount.TYPE_REPLIES, None, None).scope_totals()
                replies_this_month = DailyCount.get_by_user(
                    org, users, DailyCount.TYPE_REPLIES, *month_range(0)
                ).scope_totals()
                replies_last_month = DailyCount.get_by_user(
                    org, users, DailyCount.TYPE_REPLIES, *month_range(-1)
                ).scope_totals()

                cases_total = DailyCount.get_by_user(
                    org, users, DailyCount.TYPE_CASE_OPENED, None, None
                ).scope_totals()
                cases_opened_this_month = DailyCount.get_by_user(
                    org, users, DailyCount.TYPE_CASE_OPENED, *month_range(0)
                ).scope_totals()
                cases_closed_this_month = DailyCount.get_by_user(
                    org, users, DailyCount.TYPE_CASE_CLOSED, *month_range(0)
                ).scope_totals()

            def as_json(user):
                obj = user.as_json(full=True, org=org)
                if with_activity:
                    obj.update(
                        {
                            "replies": {
                                "this_month": replies_this_month.get(user, 0),
                                "last_month": replies_last_month.get(user, 0),
                                "total": replies_total.get(user, 0),
                            },
                            "cases": {
                                "opened_this_month": cases_opened_this_month.get(user, 0),
                                "closed_this_month": cases_closed_this_month.get(user, 0),
                                "total": cases_total.get(user, 0),
                            },
                        }
                    )

                return obj

            return JsonResponse({"results": [as_json(u) for u in users]})
