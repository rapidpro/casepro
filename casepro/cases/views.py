from __future__ import absolute_import, unicode_literals
from calendar import month_name
from dash.orgs.models import Org, TaskState
from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from datetime import date, timedelta
from django.core.cache import cache
from django.db.models import Count
from django.db.transaction import non_atomic_requests
from django.http import HttpResponse, JsonResponse
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from el_pagination.paginators import LazyPaginator
from smartmin.views import SmartCRUDL, SmartListView, SmartCreateView, SmartReadView
from smartmin.views import SmartUpdateView, SmartDeleteView, SmartTemplateView
from temba_client.utils import parse_iso8601

from casepro.contacts.models import Group
from casepro.msgs.models import Label, Message, MessageFolder, Outgoing, OutgoingFolder
from casepro.utils import parse_csv, json_encode, datetime_to_microseconds, microseconds_to_datetime, JSONEncoder
from casepro.utils import month_range
from casepro.utils.export import BaseDownloadView

from . import MAX_MESSAGE_CHARS
from .forms import PartnerForm
from .models import AccessLevel, Case, CaseFolder, CaseExport, Partner
from .tasks import case_export


class CaseSearchMixin(object):
    def derive_search(self):
        """
        Collects and prepares case search parameters into JSON serializable dict
        """
        params = self.request.GET
        folder = CaseFolder[params['folder']]
        assignee = params.get('assignee')
        after = parse_iso8601(params.get('after'))
        before = parse_iso8601(params.get('before'))

        return {'folder': folder, 'assignee': assignee, 'after': after, 'before': before}


class CaseCRUDL(SmartCRUDL):
    model = Case
    actions = ('read', 'open', 'update_summary', 'reply', 'fetch', 'search', 'timeline',
               'note', 'reassign', 'close', 'reopen', 'label')

    class Read(OrgObjPermsMixin, SmartReadView):
        fields = ()

        def has_permission(self, request, *args, **kwargs):
            has_perm = super(CaseCRUDL.Read, self).has_permission(request, *args, **kwargs)
            return has_perm and self.get_object().access_level(self.request.user) >= AccessLevel.read

        def derive_queryset(self, **kwargs):
            return Case.get_all(self.request.org).select_related('org', 'assignee')

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Read, self).get_context_data(**kwargs)
            org = self.request.org

            labels = Label.get_all(self.request.org).order_by('name')
            partners = Partner.get_all(org).order_by('name')

            can_update = self.get_object().access_level(self.request.user) == AccessLevel.update

            # angular app requires context data in JSON format
            context['context_data_json'] = json_encode({
                'case_obj': self.object.as_json(full_contact=True),
                'all_labels': [l.as_json() for l in labels],
                'all_partners': [p.as_json() for p in partners]
            })

            context['max_msg_chars'] = MAX_MESSAGE_CHARS
            context['can_update'] = can_update
            context['alert'] = self.request.GET.get('alert', None)
            return context

    class Open(OrgPermsMixin, SmartCreateView):
        """
        JSON endpoint for opening a new case. Takes a message backend id.
        """
        permission = 'cases.case_create'

        def post(self, request, *args, **kwargs):
            summary = request.POST['summary']

            assignee_id = request.POST.get('assignee', None)
            if assignee_id:
                assignee = Partner.get_all(request.org).get(pk=assignee_id)
            else:
                assignee = request.user.get_partner(self.request.org)

            message_id = int(request.POST['message'])
            message = Message.objects.get(org=request.org, backend_id=message_id)

            case = Case.get_or_open(request.org, request.user, message, summary, assignee)

            return JsonResponse({'case': case.as_json(), 'is_new': case.is_new}, encoder=JSONEncoder)

    class Note(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for adding a note to a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.POST['note']

            case.add_note(request.user, note)
            return HttpResponse(status=204)

    class Reassign(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for re-assigning a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            assignee = Partner.get_all(request.org).get(pk=request.POST['assignee'])
            case = self.get_object()
            case.reassign(request.user, assignee)
            return HttpResponse(status=204)

    class Close(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for closing a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.POST.get('note', None)
            case.close(request.user, note)

            return HttpResponse(status=204)

    class Reopen(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for re-opening a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.POST.get('note', None)

            case.reopen(request.user, note)
            return HttpResponse(status=204)

    class Label(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for labelling a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            label_ids = parse_csv(request.POST.get('labels', ''), as_ints=True)
            labels = Label.get_all(request.org).filter(pk__in=label_ids)

            case.update_labels(request.user, labels)
            return HttpResponse(status=204)

    class UpdateSummary(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for updating a case summary
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            summary = request.POST['summary']
            case.update_summary(request.user, summary)
            return HttpResponse(status=204)

    class Reply(OrgObjPermsMixin, SmartUpdateView):
        """
        JSON endpoint for replying in a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            outgoing = case.reply(request.user, request.POST['text'])
            return JsonResponse({'id': outgoing.pk})

    class Fetch(OrgObjPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching a single case
        """
        permission = 'cases.case_read'

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse(self.object.as_json(), encoder=JSONEncoder)

    class Search(OrgPermsMixin, CaseSearchMixin, SmartTemplateView):
        """
        JSON endpoint for searching for cases
        """
        permission = 'cases.case_list'

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Search, self).get_context_data(**kwargs)

            org = self.request.org
            user = self.request.user
            page = int(self.request.GET.get('page', 1))

            search = self.derive_search()
            cases = Case.search(org, user, search)
            paginator = LazyPaginator(cases, 50)

            context['object_list'] = paginator.page(page)
            context['has_more'] = paginator.num_pages > page
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({
                'results': [c.as_json() for c in context['object_list']],
                'has_more': context['has_more']
            }, encoder=JSONEncoder)

    class Timeline(OrgObjPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching case actions and messages
        """
        permission = 'cases.case_read'

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Timeline, self).get_context_data(**kwargs)
            dt_now = now()
            empty = False

            after = self.request.GET.get('after', None)
            if after:
                after = microseconds_to_datetime(int(after))
                merge_from_backend = False
            else:
                # this is the initial request for the complete timeline
                after = self.object.initial_message.created_on
                merge_from_backend = True

            if self.object.closed_on:
                if after > self.object.closed_on:
                    empty = True

                # don't return anything after a case close event
                before = self.object.closed_on
            else:
                before = dt_now

            timeline = self.object.get_timeline(after, before, merge_from_backend) if not empty else []

            context['timeline'] = timeline
            context['max_time'] = datetime_to_microseconds(dt_now)
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({'results': context['timeline'], 'max_time': context['max_time']}, encoder=JSONEncoder)


class CaseExportCRUDL(SmartCRUDL):
    model = CaseExport
    actions = ('create', 'read')

    class Create(OrgPermsMixin, CaseSearchMixin, SmartCreateView):
        @non_atomic_requests
        def post(self, request, *args, **kwargs):
            search = self.derive_search()
            export = self.model.create(self.request.org, self.request.user, search)

            case_export.delay(export.pk)

            return JsonResponse({'export_id': export.pk})

    class Read(BaseDownloadView):
        title = _("Download Cases")
        filename = 'case_export.xls'


class PartnerFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(PartnerFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.user.get_org()
        return kwargs


class PartnerCRUDL(SmartCRUDL):
    actions = ('create', 'read', 'update', 'delete', 'list', 'users')
    model = Partner

    class Create(OrgPermsMixin, PartnerFormMixin, SmartCreateView):
        form_class = PartnerForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            restricted = data['restricted']
            labels = data['labels'] if restricted else []

            self.object = Partner.create(org, data['name'], restricted, labels, data['logo'])

    class Update(OrgObjPermsMixin, PartnerFormMixin, SmartUpdateView):
        form_class = PartnerForm
        success_url = 'id@cases.partner_read'

        def has_permission(self, request, *args, **kwargs):
            return request.user.can_manage(self.get_object())

    class Read(OrgObjPermsMixin, SmartReadView):
        def get_queryset(self):
            return Partner.get_all(self.request.org)

        def get_context_data(self, **kwargs):
            context = super(PartnerCRUDL.Read, self).get_context_data(**kwargs)

            # angular app requires context data in JSON format
            context['context_data_json'] = json_encode({
                'partner': self.object.as_json(),
                'replies_by_month': self.get_replies_by_month(self.object)
            })

            user_partner = self.request.user.get_partner(self.object.org)

            context['can_manage'] = self.request.user.can_manage(self.object)
            context['can_view_replies'] = not user_partner or user_partner == self.object
            context['labels'] = self.object.get_labels()
            context['summary'] = self.get_summary(self.object)
            return context

        def get_summary(self, partner):
            return {
                'total_replies': Outgoing.objects.filter(org=partner.org, partner=partner).count(),
                'cases_open': Case.objects.filter(org=partner.org, assignee=partner, closed_on=None).count(),
                'cases_closed': Case.objects.filter(org=partner.org, assignee=partner).exclude(closed_on=None).count()
            }

        def get_replies_by_month(self, partner):
            since = month_range(-5)[0]  # last six months ago including this month

            outgoing = Outgoing.objects.filter(org=partner.org, partner=partner, created_on__gte=since)
            outgoing = outgoing.extra(select={'month': 'EXTRACT(month FROM created_on)'})
            outgoing = outgoing.values('month').annotate(replies=Count('created_on'))

            replies_by_month = {int(c['month']): c['replies'] for c in outgoing}

            # generate labels and series over last six months
            labels = []
            series = []
            this_month = date.today().month
            for m in reversed(range(0, -6, -1)):
                month = this_month + m
                if month < 1:
                    month += 12
                labels.append(month_name[month])
                series.append(replies_by_month.get(month, 0))

            return labels, series

    class Delete(OrgObjPermsMixin, SmartDeleteView):
        cancel_url = '@cases.partner_list'

        def post(self, request, *args, **kwargs):
            partner = self.get_object()
            partner.release()
            return HttpResponse(status=204)

    class List(OrgPermsMixin, SmartListView):
        paginate_by = None

        def get_queryset(self, **kwargs):
            return Partner.get_all(self.request.org).order_by('name')

    class Users(OrgPermsMixin, SmartReadView):
        """
        JSON endpoint to fetch partner users with their activity information
        """
        def get(self, request, *args, **kwargs):
            partner = self.get_object()
            managers = set(partner.get_managers())
            all_users = list(partner.get_users().order_by('profile__full_name'))

            # get reply statistics
            total = Outgoing.get_user_reply_counts(partner.org, partner, None, None)
            this_month = Outgoing.get_user_reply_counts(partner.org, partner, *month_range(0))
            last_month = Outgoing.get_user_reply_counts(partner.org, partner, *month_range(-1))

            def as_json(user):
                obj = user.as_json()
                obj.update({
                    'role': "Manager" if user in managers else "Analyst",
                    'replies': {
                        'this_month': this_month.get(user.pk, 0),
                        'last_month': last_month.get(user.pk, 0),
                        'total': total.get(user.pk, 0)
                    }
                })
                return obj

            return JsonResponse({'results': [as_json(u) for u in all_users]})


class BaseHomeView(OrgPermsMixin, SmartTemplateView):
    """
    Mixin to add site metadata to the context in JSON format which can then used
    """
    title = None
    folder = None
    folder_icon = None
    template_name = None
    permission = 'orgs.org_inbox'

    def get_context_data(self, **kwargs):
        context = super(BaseHomeView, self).get_context_data(**kwargs)
        org = self.request.org
        user = self.request.user
        partner = user.get_partner(org)

        labels = Label.get_all(org, user).order_by('name')
        partners = Partner.get_all(org).order_by('name')
        groups = Group.get_all(org, visible=True).order_by('name')

        # angular app requires context data in JSON format
        context['context_data_json'] = json_encode({
            'user': {'id': user.pk, 'partner': partner.as_json() if partner else None},
            'partners': [p.as_json() for p in partners],
            'labels': [l.as_json() for l in labels],
            'groups': [g.as_json() for g in groups],
        })

        context['banner_text'] = org.get_banner_text()
        context['folder'] = self.folder.name
        context['folder_icon'] = self.folder_icon
        context['open_case_count'] = Case.get_open(org, user).count()
        context['closed_case_count'] = Case.get_closed(org, user).count()
        return context


class InboxView(BaseHomeView):
    """
    Inbox view
    """
    title = _("Inbox")
    folder = MessageFolder.inbox
    folder_icon = 'glyphicon-inbox'
    template_name = 'cases/home_messages.haml'


class FlaggedView(BaseHomeView):
    """
    Inbox view
    """
    title = _("Flagged")
    folder = MessageFolder.flagged
    folder_icon = 'glyphicon-flag'
    template_name = 'cases/home_messages.haml'


class ArchivedView(BaseHomeView):
    """
    Archived messages view
    """
    title = _("Archived")
    folder = MessageFolder.archived
    folder_icon = 'glyphicon-trash'
    template_name = 'cases/home_messages.haml'


class UnlabelledView(BaseHomeView):
    """
    Unlabelled messages view
    """
    title = _("Unlabelled")
    folder = MessageFolder.unlabelled
    folder_icon = 'glyphicon-bullhorn'
    template_name = 'cases/home_messages.haml'


class SentView(BaseHomeView):
    """
    Outgoing messages view
    """
    title = _("Sent")
    folder = OutgoingFolder.sent
    folder_icon = 'glyphicon-send'
    template_name = 'cases/home_outgoing.haml'


class OpenCasesView(BaseHomeView):
    """
    Open cases view
    """
    title = _("Open Cases")
    folder = CaseFolder.open
    folder_icon = 'glyphicon-folder-open'
    template_name = 'cases/home_cases.haml'


class ClosedCasesView(BaseHomeView):
    """
    Closed cases view
    """
    title = _("Closed Cases")
    folder = CaseFolder.closed
    folder_icon = 'glyphicon-folder-close'
    template_name = 'cases/home_cases.haml'


class StatusView(View):
    """
    Status endpoint for keyword-based up-time monitoring checks
    """
    def get(self, request, *args, **kwargs):
        def status_check(callback):
            try:
                callback()
                return 'OK'
            except Exception:
                return 'ERROR'

        # hit Redis
        cache_status = status_check(lambda: cache.get('xxxxxx'))

        # check for failing org tasks
        org_tasks = "ERROR" if TaskState.get_failing().exists() else "OK"

        # check for unhandled messages older than 1 hour
        an_hour_ago = now() - timedelta(hours=1)
        old_unhandled = 0
        for org in Org.objects.filter(is_active=True):
            old_unhandled += Message.get_unhandled(org).filter(created_on__lt=an_hour_ago).count()

        return JsonResponse({
            'cache': cache_status,
            'org_tasks': org_tasks,
            'unhandled': old_unhandled
        }, encoder=JSONEncoder)


class PingView(View):
    """
    Ping endpoint for ELB health check pings
    """
    def get(self, request, *args, **kwargs):
        try:
            # hit the db and Redis
            Org.objects.first()
            cache.get('xxxxxx')
        except Exception:
            return HttpResponse("ERROR", status=500)

        return HttpResponse("OK", status=200)
