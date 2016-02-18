from __future__ import absolute_import, unicode_literals

from casepro.contacts.models import Group
from casepro.msgs.views import MessageView, MessageSearchMixin
from casepro.utils import parse_csv, json_encode, normalize, datetime_to_microseconds, microseconds_to_datetime
from dash.orgs.models import Org, TaskState
from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from django import forms
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from enum import Enum
from smartmin.views import SmartCRUDL, SmartListView, SmartCreateView, SmartReadView
from smartmin.views import SmartUpdateView, SmartDeleteView, SmartTemplateView
from temba_client.utils import parse_iso8601
from . import MAX_MESSAGE_CHARS
from .models import AccessLevel, Case, Label, RemoteMessage, MessageAction, Partner, Outgoing


class CaseView(Enum):
    open = 1
    closed = 2


class CaseCRUDL(SmartCRUDL):
    model = Case
    actions = ('read', 'open', 'update_summary', 'fetch', 'search', 'timeline',
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
        JSON endpoint for opening a new case
        """
        permission = 'cases.case_create'

        def post(self, request, *args, **kwargs):
            message_id = int(request.POST['message'])
            summary = request.POST['summary']

            assignee_id = request.POST.get('assignee', None)
            assignee = Partner.get_all(request.org).get(pk=assignee_id) if assignee_id else request.user.get_partner()

            # TODO this should lookup a local message once they exist

            # fetch message from RapidPro to get its current labels
            client = request.org.get_temba_client(api_version=2)
            message = client.get_messages(id=message_id).first()
            labels = Label.get_all(request.org).filter(uuid__in=[l.uuid for l in message.labels])

            case = Case.get_or_open(request.org, request.user, labels, message, summary, assignee)

            return JsonResponse({'case': case.as_json(), 'is_new': case.is_new})

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
            assignee = Partner.get_all(request.org).get(pk=request.POST['assignee_id'])
            case = self.get_object()
            case.reassign(request.user, assignee)
            return HttpResponse(status=204)

    class Close(OrgPermsMixin, SmartUpdateView):
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

    class Fetch(OrgPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching a single case
        """
        permission = 'cases.case_read'

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse(self.object.as_json())

    class Search(OrgPermsMixin, SmartListView):
        """
        JSON endpoint for searching for cases
        """
        permission = 'cases.case_list'
        paginate_by = 25

        def derive_queryset(self, **kwargs):
            label_id = self.request.GET.get('label', None)
            view = CaseView[self.request.GET['view']]
            assignee_id = self.request.GET.get('assignee', None)

            before = self.request.REQUEST.get('before', None)
            after = self.request.REQUEST.get('after', None)

            label = Label.objects.get(pk=label_id) if label_id else None

            assignee = Partner.get_all(self.request.org).get(pk=assignee_id) if assignee_id else None

            if view == CaseView.open:
                qs = Case.get_open(self.request.org, user=self.request.user, label=label)
            elif view == CaseView.closed:
                qs = Case.get_closed(self.request.org, user=self.request.user, label=label)
            else:
                raise ValueError('Invalid item view for cases')

            if assignee:
                qs = qs.filter(assignee=assignee)

            if before:
                qs = qs.filter(opened_on__lt=parse_iso8601(before))
            if after:
                qs = qs.filter(opened_on__gt=parse_iso8601(after))

            return qs.prefetch_related('labels').select_related('assignee').order_by('-pk')

        def render_to_response(self, context, **response_kwargs):
            count = context['paginator'].count
            has_more = context['page_obj'].has_next()
            results = [obj.as_json() for obj in list(context['object_list'])]

            return JsonResponse({'results': results, 'has_more': has_more, 'total': count})

    class Timeline(OrgPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching case actions and messages
        """
        permission = 'cases.case_read'

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Timeline, self).get_context_data(**kwargs)
            now = timezone.now()
            empty = False

            after = self.request.GET.get('after', None)
            if after:
                after = microseconds_to_datetime(int(after))
            else:
                after = self.object.message_on

            if self.object.closed_on:
                if after > self.object.closed_on:
                    empty = True

                # don't return anything after a case close event
                before = self.object.closed_on
            else:
                before = now

            timeline = self.object.get_timeline(after, before) if not empty else []

            context['timeline'] = timeline
            context['max_time'] = datetime_to_microseconds(now)
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({'results': context['timeline'], 'max_time': context['max_time']})


class LabelForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)

    description = forms.CharField(label=_("Description"), max_length=255, widget=forms.Textarea)

    keywords = forms.CharField(label=_("Keywords"), widget=forms.Textarea, required=False,
                               help_text=_("Match messages containing any of these words"))

    partners = forms.ModelMultipleChoiceField(label=_("Visible to"), queryset=Partner.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')

        super(LabelForm, self).__init__(*args, **kwargs)

        self.fields['partners'].queryset = Partner.get_all(org)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if name.lower() == 'flagged':
            raise forms.ValidationError(_("Reserved label name"))
        elif name.startswith('+') or name.startswith('-'):
            raise forms.ValidationError(_("Label name cannot start with + or -"))
        return name

    def clean_keywords(self):
        keywords = parse_csv(self.cleaned_data['keywords'])
        clean_keywords = []
        for keyword in keywords:
            clean_keyword = normalize(keyword)

            if len(keyword) < Label.KEYWORD_MIN_LENGTH:
                raise forms.ValidationError(_("Keywords must be at least %d characters long")
                                            % Label.KEYWORD_MIN_LENGTH)

            if not Label.is_valid_keyword(keyword):
                raise forms.ValidationError(_("Invalid keyword: %s") % keyword)

            clean_keywords.append(clean_keyword)

        return ','.join(clean_keywords)

    class Meta:
        model = Label
        fields = ('name', 'description', 'keywords', 'partners')


class LabelFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(LabelFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.user.get_org()
        return kwargs


class LabelCRUDL(SmartCRUDL):
    actions = ('create', 'update', 'delete', 'list')
    model = Label

    class Create(OrgPermsMixin, LabelFormMixin, SmartCreateView):
        form_class = LabelForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            name = data['name']
            description = data['description']
            words = parse_csv(data['keywords'])
            partners = data['partners']
            self.object = Label.create(org, name, description, words, partners)

    class Update(OrgObjPermsMixin, LabelFormMixin, SmartUpdateView):
        form_class = LabelForm

        def derive_initial(self):
            initial = super(LabelCRUDL.Update, self).derive_initial()
            initial['keywords'] = ', '.join(self.object.get_keywords())
            return initial

        def post_save(self, obj):
            obj.update_name(obj.name)
            return obj

    class Delete(OrgObjPermsMixin, SmartDeleteView):
        cancel_url = '@cases.label_list'

        def post(self, request, *args, **kwargs):
            label = self.get_object()
            label.release()
            return HttpResponse(status=204)

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'description', 'partners')
        default_order = ('name',)

        def derive_queryset(self, **kwargs):
            qs = super(LabelCRUDL.List, self).derive_queryset(**kwargs)
            qs = qs.filter(org=self.request.org, is_active=True)
            return qs

        def get_partners(self, obj):
            return ', '.join([p.name for p in obj.get_partners()])


class MessageSearchView(OrgPermsMixin, MessageSearchMixin, SmartTemplateView):
    """
    JSON endpoint for fetching messages
    """
    permission = 'orgs.org_inbox'

    def get_context_data(self, **kwargs):
        context = super(MessageSearchView, self).get_context_data(**kwargs)

        search = self.derive_search()
        page = int(self.request.GET.get('page', 0))

        client = self.request.org.get_temba_client()
        pager = client.pager(start_page=page) if page else None
        messages = RemoteMessage.search(self.request.org, search, pager)

        context['messages'] = messages

        if page:
            context['page'] = page
            context['has_more'] = pager.has_more()
            context['total'] = pager.total
        else:
            context['page'] = None
            context['has_more'] = None
            context['total'] = len(messages)

        return context

    def render_to_response(self, context, **response_kwargs):
        label_map = {l.name: l for l in Label.get_all(self.request.org)}

        results = [RemoteMessage.as_json(m, label_map) for m in context['messages']]

        return JsonResponse({'results': results, 'has_more': context['has_more'], 'total': context['total']})


class MessageActionView(OrgPermsMixin, View):
    """
    AJAX endpoint for bulk message actions. Takes a list of message ids.
    """
    permission = 'orgs.org_inbox'

    def post(self, request, *args, **kwargs):
        org = self.request.org
        user = self.request.user

        action = kwargs['action']
        message_ids = parse_csv(self.request.POST.get('messages', ''), as_ints=True)
        label_id = int(self.request.POST.get('label', 0))
        label = Label.get_all(org, user).get(pk=label_id) if label_id else None

        if action == 'flag':
            RemoteMessage.bulk_flag(org, user, message_ids)
        elif action == 'unflag':
            RemoteMessage.bulk_unflag(org, user, message_ids)
        elif action == 'label':
            RemoteMessage.bulk_label(org, user, message_ids, label)
        elif action == 'unlabel':
            RemoteMessage.bulk_unlabel(org, user, message_ids, label)
        elif action == 'archive':
            RemoteMessage.bulk_archive(org, user, message_ids)
        elif action == 'restore':
            RemoteMessage.bulk_restore(org, user, message_ids)
        else:
            return HttpResponseBadRequest("Invalid action: %s", action)

        return HttpResponse(status=204)


class MessageLabelView(OrgPermsMixin, View):
    """
    AJAX endpoint for labelling a message.
    """
    permission = 'orgs.org_inbox'

    def post(self, request, *args, **kwargs):
        org = self.request.org
        user = self.request.user
        message = org.get_temba_client().get_message(int(kwargs['id']))
        label_ids = parse_csv(self.request.POST.get('labels', ''), as_ints=True)
        labels = Label.get_all(org, user).filter(pk__in=label_ids)

        RemoteMessage.update_labels(message, org, user, labels)
        return HttpResponse(status=204)


class MessageSendView(OrgPermsMixin, View):
    """
    JSON endpoint for message sending. Takes a list of contact UUIDs or URNs
    """
    permission = 'orgs.org_inbox'

    def post(self, request, *args, **kwargs):
        activity = request.POST['activity']
        text = request.POST['text']
        urns = parse_csv(request.POST.get('urns', ''), as_ints=False)
        contacts = parse_csv(request.POST.get('contacts', ''), as_ints=False)
        case_id = request.POST.get('case', None)
        case = Case.objects.get(org=request.org, pk=case_id) if case_id else None

        outgoing = Outgoing.create(request.org, request.user, activity, text, urns=urns, contacts=contacts, case=case)

        return JsonResponse({'id': outgoing.pk})


class MessageHistoryView(OrgPermsMixin, View):
    """
    JSON endpoint for fetching message history. Takes a message id
    """
    permission = 'orgs.org_inbox'

    def get(self, request, *args, **kwargs):
        actions = MessageAction.get_by_message(self.request.org, int(kwargs['id'])).order_by('-pk')
        actions = [a.as_json() for a in actions]
        return JsonResponse({'actions': actions})


class PartnerForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')
        super(PartnerForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Partner
        fields = ('name', 'logo')


class PartnerFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(PartnerFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.user.get_org()
        return kwargs


class PartnerCRUDL(SmartCRUDL):
    actions = ('create', 'read', 'update', 'delete', 'list')
    model = Partner

    class Create(OrgPermsMixin, PartnerFormMixin, SmartCreateView):
        form_class = PartnerForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            self.object = Partner.create(org, data['name'], data['logo'])

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
            })

            context['can_manage'] = self.request.user.can_manage(self.object)
            context['labels'] = self.object.get_labels()
            context['managers'] = self.object.get_managers()
            context['analysts'] = self.object.get_analysts()
            return context

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


class BaseHomeView(OrgPermsMixin, SmartTemplateView):
    """
    Mixin to add site metadata to the context in JSON format which can then used
    """
    permission = 'orgs.org_inbox'

    def get_context_data(self, **kwargs):
        context = super(BaseHomeView, self).get_context_data(**kwargs)
        org = self.request.org
        user = self.request.user
        partner = user.get_partner()

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
        context['folder_icon'] = self.folder_icon
        context['item_view'] = self.item_view.name
        context['open_case_count'] = Case.get_open(org, user).count()
        context['closed_case_count'] = Case.get_closed(org, user).count()
        return context


class InboxView(BaseHomeView):
    """
    Inbox view
    """
    template_name = 'cases/home_messages.haml'
    title = _("Inbox")
    folder_icon = 'glyphicon-inbox'
    item_view = MessageView.inbox


class FlaggedView(BaseHomeView):
    """
    Inbox view
    """
    template_name = 'cases/home_messages.haml'
    title = _("Flagged")
    folder_icon = 'glyphicon-flag'
    item_view = MessageView.flagged


class ArchivedView(BaseHomeView):
    """
    Archived messages view
    """
    template_name = 'cases/home_messages.haml'
    title = _("Archived")
    folder_icon = 'glyphicon-trash'
    item_view = MessageView.archived


class UnlabelledView(BaseHomeView):
    """
    Unlabelled messages view
    """
    template_name = 'cases/home_messages.haml'
    title = _("Unlabelled")
    folder_icon = 'glyphicon-bullhorn'
    item_view = MessageView.unlabelled


class OpenCasesView(BaseHomeView):
    """
    Open cases view
    """
    template_name = 'cases/home_cases.haml'
    title = _("Open Cases")
    folder_icon = 'glyphicon-folder-open'
    item_view = CaseView.open


class ClosedCasesView(BaseHomeView):
    """
    Closed cases view
    """
    template_name = 'cases/home_cases.haml'
    title = _("Closed Cases")
    folder_icon = 'glyphicon-folder-close'
    item_view = CaseView.closed


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

        # hit the db and Redis
        db_status = status_check(lambda: Org.objects.first())
        cache_status = status_check(lambda: cache.get('xxxxxx'))

        org_tasks = "ERROR" if TaskState.get_failing().exists() else "OK"

        return JsonResponse({'db': db_status, 'cache': cache_status, 'org_tasks': org_tasks})


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
