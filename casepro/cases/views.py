from datetime import timedelta

from dash.orgs.models import Org, TaskState
from dash.orgs.views import OrgObjPermsMixin, OrgPermsMixin
from el_pagination.paginators import LazyPaginator
from smartmin.mixins import NonAtomicMixin
from smartmin.views import (
    SmartCreateView,
    SmartCRUDL,
    SmartDeleteView,
    SmartListView,
    SmartReadView,
    SmartTemplateView,
    SmartUpdateView,
)
from temba_client.utils import parse_iso8601

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View

from casepro.contacts.models import Contact, Field
from casepro.msgs.models import Label, Message, MessageFolder, OutgoingFolder
from casepro.statistics.models import DailyCount, DailySecondTotalCount
from casepro.utils import (
    JSONEncoder,
    datetime_to_microseconds,
    humanize_seconds,
    microseconds_to_datetime,
    month_range,
    str_to_bool,
)
from casepro.utils.export import BaseDownloadView

from .forms import PartnerCreateForm, PartnerUpdateForm
from .models import AccessLevel, Case, CaseExport, CaseFolder, Partner
from .tasks import case_export


class CaseSearchMixin(object):
    def derive_search(self):
        """
        Collects and prepares case search parameters into JSON serializable dict
        """
        params = self.request.GET
        folder = CaseFolder[params["folder"]]
        assignee = params.get("assignee")
        user_assignee = params.get("user_assignee")
        after = parse_iso8601(params.get("after"))
        before = parse_iso8601(params.get("before"))

        return {
            "folder": folder,
            "assignee": assignee,
            "user_assignee": user_assignee,
            "after": after,
            "before": before,
        }


class CaseCRUDL(SmartCRUDL):
    model = Case
    actions = (
        "read",
        "open",
        "update_summary",
        "reply",
        "fetch",
        "search",
        "timeline",
        "note",
        "reassign",
        "close",
        "reopen",
        "label",
        "watch",
        "unwatch",
    )

    class Read(OrgObjPermsMixin, SmartReadView):
        fields = ()

        def has_permission(self, request, *args, **kwargs):
            has_perm = super(CaseCRUDL.Read, self).has_permission(request, *args, **kwargs)
            return has_perm and self.get_object().access_level(self.request.user) >= AccessLevel.read

        def derive_queryset(self, **kwargs):
            return Case.get_all(self.request.org).select_related("org", "assignee")

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Read, self).get_context_data(**kwargs)
            case = self.get_object()
            can_update = case.access_level(self.request.user) == AccessLevel.update

            labels = Label.get_all(self.request.org).order_by("name")
            fields = Field.get_all(self.object.org, visible=True).order_by("label")

            # angular app requires context data in JSON format
            context["context_data_json"] = {
                "all_labels": [l.as_json() for l in labels],
                "fields": [f.as_json() for f in fields],
            }

            context["can_update"] = can_update
            context["alert"] = self.request.GET.get("alert", None)
            context["case_id"] = case.id

            return context

    class Open(OrgPermsMixin, SmartCreateView):
        """
        JSON endpoint for opening a new case. Takes a message backend id, or a URN.
        """

        permission = "cases.case_create"

        def post(self, request, *args, **kwargs):
            summary = request.json["summary"]

            assignee_id = request.json.get("assignee", None)
            user_assignee = request.json.get("user_assignee", None)
            if assignee_id:
                assignee = Partner.get_all(request.org).get(pk=assignee_id)
                if user_assignee:
                    user_assignee = get_object_or_404(assignee.get_users(), pk=user_assignee)
            else:
                assignee = request.user.get_partner(self.request.org)
                user_assignee = request.user

            message_id = request.json.get("message")
            if message_id:
                message = Message.objects.get(org=request.org, backend_id=int(message_id))
                contact = None
            else:
                message = None
                contact = Contact.get_or_create_from_urn(org=request.org, urn=request.json["urn"])

            case = Case.get_or_open(
                request.org, request.user, message, summary, assignee, user_assignee=user_assignee, contact=contact
            )

            # augment regular case JSON
            case_json = case.as_json()
            case_json["is_new"] = case.is_new
            case_json["watching"] = case.is_watched_by(request.user)

            return JsonResponse(case_json, encoder=JSONEncoder)

    class Note(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for adding a note to a case
        """

        permission = "cases.case_update"

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.json["note"]

            case.add_note(request.user, note)
            return HttpResponse(status=204)

    class Reassign(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for re-assigning a case
        """

        permission = "cases.case_update"

        def post(self, request, *args, **kwargs):
            assignee = Partner.get_all(request.org).get(pk=request.json["assignee"])
            user = request.json.get("user_assignee")
            if user is not None:
                user = get_object_or_404(assignee.get_users(), pk=user)
            case = self.get_object()
            case.reassign(request.user, assignee, user_assignee=user)
            return HttpResponse(status=204)

    class Close(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for closing a case
        """

        permission = "cases.case_update"

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.json.get("note")
            case.close(request.user, note)

            return HttpResponse(status=204)

    class Reopen(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for re-opening a case
        """

        permission = "cases.case_update"

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.json.get("note")

            case.reopen(request.user, note)
            return HttpResponse(status=204)

    class Label(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for labelling a case
        """

        permission = "cases.case_update"

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            user = request.user
            user_labels = Label.get_all(self.org, user)

            label_ids = request.json["labels"]
            specified_labels = list(user_labels.filter(pk__in=label_ids))

            # user can't remove labels that they can't see
            unseen_labels = [l for l in case.labels.all() if l not in user_labels]

            case.update_labels(user, specified_labels + unseen_labels)
            return HttpResponse(status=204)

    class UpdateSummary(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for updating a case summary
        """

        permission = "cases.case_update"

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            summary = request.json["summary"]
            case.update_summary(request.user, summary)
            return HttpResponse(status=204)

    class Reply(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for replying in a case
        """

        permission = "cases.case_update"

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            outgoing = case.reply(request.user, request.json["text"])
            return JsonResponse({"id": outgoing.pk})

    class Fetch(OrgObjPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching a single case
        """

        permission = "cases.case_read"

        def render_to_response(self, context, **response_kwargs):
            case_json = self.object.as_json()

            # augment usual case JSON
            case_json["watching"] = self.object.is_watched_by(self.request.user)

            return JsonResponse(case_json, encoder=JSONEncoder)

    class Search(OrgPermsMixin, CaseSearchMixin, SmartTemplateView):
        """
        JSON endpoint for searching for cases
        """

        permission = "cases.case_list"

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Search, self).get_context_data(**kwargs)

            org = self.request.org
            user = self.request.user
            page = int(self.request.GET.get("page", 1))

            search = self.derive_search()
            cases = Case.search(org, user, search)
            paginator = LazyPaginator(cases, 50)

            context["object_list"] = paginator.page(page)
            context["has_more"] = paginator.num_pages > page
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse(
                {"results": [c.as_json() for c in context["object_list"]], "has_more": context["has_more"]},
                encoder=JSONEncoder,
            )

    class Timeline(OrgObjPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching case actions and messages
        """

        permission = "cases.case_read"

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Timeline, self).get_context_data(**kwargs)
            dt_now = now()
            empty = False

            after = self.request.GET.get("after", None)
            if after:
                after = microseconds_to_datetime(int(after))
                merge_from_backend = False
            else:
                # this is the initial request for the complete timeline
                if self.object.initial_message is not None:
                    after = self.object.initial_message.created_on
                else:
                    after = self.object.opened_on
                merge_from_backend = True

            if self.object.closed_on:
                if after > self.object.closed_on:
                    empty = True

                # don't return anything after a case close event
                before = self.object.closed_on
            else:
                before = dt_now

            timeline = self.object.get_timeline(after, before, merge_from_backend) if not empty else []

            context["timeline"] = timeline
            context["max_time"] = datetime_to_microseconds(dt_now)
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({"results": context["timeline"], "max_time": context["max_time"]}, encoder=JSONEncoder)

    class Watch(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for watching a case
        """

        permission = "cases.case_read"

        def post(self, request, *args, **kwargs):
            self.get_object().watch(request.user)
            return HttpResponse(status=204)

    class Unwatch(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for unwatching a case
        """

        permission = "cases.case_read"

        def post(self, request, *args, **kwargs):
            self.get_object().unwatch(request.user)
            return HttpResponse(status=204)


class CaseExportCRUDL(SmartCRUDL):
    model = CaseExport
    actions = ("create", "read")

    class Create(NonAtomicMixin, OrgPermsMixin, CaseSearchMixin, SmartCreateView):
        def post(self, request, *args, **kwargs):
            search = self.derive_search()
            export = self.model.create(self.request.org, self.request.user, search)

            case_export.delay(export.pk)

            return JsonResponse({"export_id": export.pk})

    class Read(BaseDownloadView):
        title = _("Download Cases")
        filename = "case_export.xls"


class PartnerFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(PartnerFormMixin, self).get_form_kwargs()
        kwargs["org"] = self.request.user.get_org()
        return kwargs


class PartnerCRUDL(SmartCRUDL):
    actions = ("create", "read", "update", "delete", "list")
    model = Partner

    class Create(OrgPermsMixin, PartnerFormMixin, SmartCreateView):
        form_class = PartnerCreateForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            restricted = data["is_restricted"]
            labels = data["labels"] if restricted else []

            self.object = Partner.create(
                org, data["name"], data["description"], None, restricted, labels, data["logo"]
            )

        def get_success_url(self):
            return reverse("cases.partner_read", args=[self.object.pk])

    class Update(OrgObjPermsMixin, PartnerFormMixin, SmartUpdateView):
        form_class = PartnerUpdateForm
        success_url = "id@cases.partner_read"

        def has_permission(self, request, *args, **kwargs):
            return request.user.can_manage(self.get_object())

    class Read(OrgObjPermsMixin, SmartReadView):
        def get_queryset(self):
            return Partner.get_all(self.request.org)

        def get_context_data(self, **kwargs):
            context = super(PartnerCRUDL.Read, self).get_context_data(**kwargs)

            fields = Field.get_all(self.object.org, visible=True).order_by("label")

            # angular app requires context data in JSON format
            context["context_data_json"] = {"partner": self.object.as_json(), "fields": [f.as_json() for f in fields]}

            user_partner = self.request.user.get_partner(self.object.org)

            context["can_manage"] = self.request.user.can_manage(self.object)
            context["can_view_replies"] = not user_partner or user_partner == self.object
            context["labels"] = self.object.get_labels()
            context["summary"] = self.get_summary(self.object)
            return context

        def get_summary(self, partner):
            return {
                "total_replies": DailyCount.get_by_partner([partner], DailyCount.TYPE_REPLIES).total(),
                "cases_open": Case.objects.filter(org=partner.org, assignee=partner, closed_on=None).count(),
                "cases_closed": Case.objects.filter(org=partner.org, assignee=partner).exclude(closed_on=None).count(),
            }

    class Delete(OrgObjPermsMixin, SmartDeleteView):
        cancel_url = "@cases.partner_list"

        def post(self, request, *args, **kwargs):
            partner = self.get_object()
            partner.release()
            return HttpResponse(status=204)

    class List(OrgPermsMixin, SmartListView):
        paginate_by = None

        def get_queryset(self, **kwargs):
            return Partner.get_all(self.request.org).order_by("name")

        def render_to_response(self, context, **response_kwargs):
            if self.request.is_ajax():
                with_activity = str_to_bool(self.request.GET.get("with_activity", ""))
                return self.render_as_json(context["object_list"], with_activity)
            else:
                return super(PartnerCRUDL.List, self).render_to_response(context, **response_kwargs)

        def render_as_json(self, partners, with_activity):
            if with_activity:
                # get reply statistics
                replies_total = DailyCount.get_by_partner(partners, DailyCount.TYPE_REPLIES, None, None).scope_totals()
                replies_this_month = DailyCount.get_by_partner(
                    partners, DailyCount.TYPE_REPLIES, *month_range(0)
                ).scope_totals()
                replies_last_month = DailyCount.get_by_partner(
                    partners, DailyCount.TYPE_REPLIES, *month_range(-1)
                ).scope_totals()
                average_referral_response_time_this_month = DailySecondTotalCount.get_by_partner(
                    partners, DailySecondTotalCount.TYPE_TILL_REPLIED, *month_range(0)
                )
                average_referral_response_time_this_month = average_referral_response_time_this_month.scope_averages()
                average_closed_this_month = DailySecondTotalCount.get_by_partner(
                    partners, DailySecondTotalCount.TYPE_TILL_CLOSED, *month_range(0)
                )
                average_closed_this_month = average_closed_this_month.scope_averages()

                # get cases statistics
                cases_total = DailyCount.get_by_partner(
                    partners, DailyCount.TYPE_CASE_OPENED, None, None
                ).scope_totals()
                cases_opened_this_month = DailyCount.get_by_partner(
                    partners, DailyCount.TYPE_CASE_OPENED, *month_range(0)
                ).scope_totals()
                cases_closed_this_month = DailyCount.get_by_partner(
                    partners, DailyCount.TYPE_CASE_CLOSED, *month_range(0)
                ).scope_totals()

            def as_json(partner):
                obj = partner.as_json()
                if with_activity:
                    obj.update(
                        {
                            "replies": {
                                "this_month": replies_this_month.get(partner, 0),
                                "last_month": replies_last_month.get(partner, 0),
                                "total": replies_total.get(partner, 0),
                                "average_referral_response_time_this_month": humanize_seconds(
                                    average_referral_response_time_this_month.get(partner, 0)
                                ),
                            },
                            "cases": {
                                "average_closed_this_month": humanize_seconds(
                                    average_closed_this_month.get(partner, 0)
                                ),
                                "opened_this_month": cases_opened_this_month.get(partner, 0),
                                "closed_this_month": cases_closed_this_month.get(partner, 0),
                                "total": cases_total.get(partner, 0),
                            },
                        }
                    )
                return obj

            return JsonResponse({"results": [as_json(p) for p in partners]})


class BaseInboxView(OrgPermsMixin, SmartTemplateView):
    """
    Mixin to add site metadata to the context in JSON format which can then used
    """

    title = None
    folder = None
    folder_icon = None
    template_name = None
    permission = "orgs.org_inbox"

    def get_context_data(self, **kwargs):
        context = super(BaseInboxView, self).get_context_data(**kwargs)
        org = self.request.org
        user = self.request.user
        partner = user.get_partner(org)

        labels = list(Label.get_all(org, user).order_by("name"))
        Label.bulk_cache_initialize(labels)

        fields = Field.get_all(org, visible=True).order_by("label")

        # angular app requires context data in JSON format
        context["context_data_json"] = {
            "user": {"id": user.pk, "partner": partner.as_json() if partner else None},
            "labels": [l.as_json() for l in labels],
            "fields": [f.as_json() for f in fields],
        }

        context["banner_text"] = org.get_banner_text()
        context["folder"] = self.folder.name
        context["folder_icon"] = self.folder_icon
        context["open_case_count"] = Case.get_open(org, user).count()
        context["closed_case_count"] = Case.get_closed(org, user).count()
        context["allow_case_without_message"] = getattr(settings, "SITE_ALLOW_CASE_WITHOUT_MESSAGE", False)
        context["user_must_reply_with_faq"] = org and not user.is_anonymous and user.must_use_faq()
        context["site_contact_display"] = getattr(settings, "SITE_CONTACT_DISPLAY", "name")
        context["search_text_days"] = Message.SEARCH_BY_TEXT_DAYS
        return context


class InboxView(BaseInboxView):
    """
    Inbox view
    """

    title = _("Inbox")
    folder = MessageFolder.inbox
    folder_icon = "glyphicon-inbox"
    template_name = "cases/inbox_messages.haml"


class FlaggedView(BaseInboxView):
    """
    Inbox view
    """

    title = _("Flagged")
    folder = MessageFolder.flagged
    folder_icon = "glyphicon-flag"
    template_name = "cases/inbox_messages.haml"


class ArchivedView(BaseInboxView):
    """
    Archived messages view
    """

    title = _("Archived")
    folder = MessageFolder.archived
    folder_icon = "glyphicon-trash"
    template_name = "cases/inbox_messages.haml"


class UnlabelledView(BaseInboxView):
    """
    Unlabelled messages view
    """

    title = _("Unlabelled")
    folder = MessageFolder.unlabelled
    folder_icon = "glyphicon-bullhorn"
    template_name = "cases/inbox_messages.haml"


class SentView(BaseInboxView):
    """
    Outgoing messages view
    """

    title = _("Sent")
    folder = OutgoingFolder.sent
    folder_icon = "glyphicon-send"
    template_name = "cases/inbox_outgoing.haml"


class OpenCasesView(BaseInboxView):
    """
    Open cases view
    """

    title = _("Open Cases")
    folder = CaseFolder.open
    folder_icon = "glyphicon-folder-open"
    template_name = "cases/inbox_cases.haml"


class ClosedCasesView(BaseInboxView):
    """
    Closed cases view
    """

    title = _("Closed Cases")
    folder = CaseFolder.closed
    folder_icon = "glyphicon-folder-close"
    template_name = "cases/inbox_cases.haml"


class StatusView(View):
    """
    Status endpoint for keyword-based up-time monitoring checks
    """

    def get(self, request, *args, **kwargs):
        def status_check(callback):
            try:
                callback()
                return "OK"
            except Exception:
                return "ERROR"

        # hit Redis
        cache_status = status_check(lambda: cache.get("xxxxxx"))

        # check for failing org tasks
        org_tasks = "ERROR" if TaskState.get_failing().exists() else "OK"

        # check for unhandled messages older than 1 hour
        an_hour_ago = now() - timedelta(hours=1)
        old_unhandled = 0
        for org in Org.objects.filter(is_active=True):
            old_unhandled += Message.get_unhandled(org).filter(created_on__lt=an_hour_ago).count()

        return JsonResponse(
            {"cache": cache_status, "org_tasks": org_tasks, "unhandled": old_unhandled}, encoder=JSONEncoder
        )


class PingView(View):
    """
    Ping endpoint for ELB health check pings
    """

    def get(self, request, *args, **kwargs):
        try:
            # hit the db and Redis
            Org.objects.first()
            cache.get("xxxxxx")
        except Exception:
            return HttpResponse("ERROR", status=500)

        return HttpResponse("OK", status=200)
