from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from dash.utils import get_obj_cacheable
from django import forms
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, JsonResponse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from smartmin.users.views import SmartCRUDL, SmartListView, SmartCreateView, SmartReadView, SmartFormView
from smartmin.users.views import SmartUpdateView, SmartDeleteView, SmartTemplateView
from temba.utils import parse_iso8601
from . import parse_csv, json_encode, contact_as_json, MAX_MESSAGE_CHARS
from .models import Case, Group, Label, Message, MessageExport, Partner
from .tasks import message_export


class CaseCRUDL(SmartCRUDL):
    model = Case
    actions = ('read', 'open', 'note', 'reassign', 'close', 'reopen', 'label', 'fetch', 'search', 'timeline')

    class Read(OrgObjPermsMixin, SmartReadView):
        fields = ()

        def has_permission(self, request, *args, **kwargs):
            has_perm = super(CaseCRUDL.Read, self).has_permission(request, *args, **kwargs)
            return has_perm and self.get_object().accessible_by(self.request.user)

        def derive_queryset(self, **kwargs):
            return Case.get_all(self.request.org)

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Read, self).get_context_data(**kwargs)
            org = self.request.org

            contact = self.object.fetch_contact()
            labels = Label.get_all(self.request.org).order_by('name')
            partners = Partner.get_all(org).order_by('name')

            # angular app requires context data in JSON format
            context['context_data_json'] = json_encode({
                'case': self.object.as_json(),
                'contact': contact_as_json(contact, org.get_contact_fields()) if contact else None,
                'all_labels': [l.as_json() for l in labels],
                'all_partners': [p.as_json() for p in partners]
            })

            context['max_msg_chars'] = MAX_MESSAGE_CHARS
            return context

    class Open(OrgPermsMixin, SmartCreateView):
        """
        JSON endpoint for opening a new case
        """
        permission = 'cases.case_create'

        def post(self, request, *args, **kwargs):
            message_id = int(request.POST['message_id'])
            assignee_id = request.POST['assignee_id']

            assignee = Partner.get_all(request.org).get(pk=assignee_id) if assignee_id else None

            client = request.org.get_temba_client()
            message = client.get_message(message_id)

            # map from label names to label objects
            label_map = {l.name: l for l in Label.get_all(request.org)}
            labels = [label_map[label_name] for label_name in message.labels if label_name in label_map]

            case = Case.open(request.org, request.user, labels, assignee, message)

            return JsonResponse(case.as_json())

    class Note(OrgPermsMixin, SmartUpdateView):
        """
        JSON endpoint for adding a note to a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.POST['note']

            case.note(self.request.user, note)
            return HttpResponse(status=204)

    class Reassign(OrgPermsMixin, SmartUpdateView):
        """
        JSON endpoint for re-assigning a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            assignee = Partner.get_all(request.org).get(pk=request.POST['assignee_id'])
            case = self.get_object()
            case.reassign(self.request.user, assignee)
            return HttpResponse(status=204)

    class Close(OrgPermsMixin, SmartUpdateView):
        """
        JSON endpoint for closing a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.POST.get('note', None)

            case.close(self.request.user, note)
            return HttpResponse(status=204)

    class Reopen(OrgPermsMixin, SmartUpdateView):
        """
        JSON endpoint for re-opening a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            note = request.POST.get('note', None)

            case.reopen(self.request.user, note)
            return HttpResponse(status=204)

    class Label(OrgPermsMixin, SmartUpdateView):
        """
        JSON endpoint for labelling a case
        """
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            label_ids = parse_csv(request.POST.get('labels', ''), as_ints=True)
            labels = Label.get_all(request.org).filter(pk__in=label_ids)

            case.update_labels(self.request.user, labels)
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
            status = self.request.GET.get('status', None)
            assignee_id = self.request.GET.get('assignee', None)

            before = self.request.REQUEST.get('before', None)
            after = self.request.REQUEST.get('after', None)

            labels = Label.get_all(self.request.org, self.request.user)
            if label_id:
                labels = labels.filter(pk=label_id)

            assignee = Partner.get_all(self.request.org).get(pk=assignee_id) if assignee_id else None

            if status == 'open':
                qs = Case.get_open(self.request.org, labels)
            elif status == 'closed':
                qs = Case.get_closed(self.request.org, labels)
            else:
                qs = Case.get_all(self.request.org, labels)

            if assignee:
                qs = qs.filter(assignee=assignee)

            if before:
                qs = qs.filter(opened_on__lt=parse_iso8601(before))
            if after:
                qs = qs.filter(opened_on__gt=parse_iso8601(after))

            return qs.order_by('-pk').select_related('assignee')

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
            org = self.request.org

            since_time = parse_iso8601(self.request.GET.get('since_time', None)) or self.object.message_on
            since_message_id = self.request.GET.get('since_message_id', None) or self.object.message_id
            since_action_id = self.request.GET.get('since_action_id', None) or 0

            # fetch messages
            before = self.object.closed_on
            messages = org.get_temba_client().get_messages(contacts=[self.object.contact_uuid],
                                                           after=since_time, before=before, reverse=True)

            # Temba API doesn't have a way to filter by 'after id'. Filtering by 'after time' can lead to dups due to
            # db times being higher accuracy than those returned in API JSON. Here we remove possible dups based on id.
            if since_message_id != self.object.message_id:
                messages = [m for m in messages if m.id > since_message_id]

            # fetch actions
            actions = self.object.actions.select_related('assignee', 'created_by').order_by('pk')
            if since_action_id:
                actions = actions.filter(pk__gt=since_action_id)

            label_map = {l.name: l for l in Label.get_all(self.request.org)}

            timeline = [{'time': m.created_on, 'type': 'M', 'item': Message.as_json(m, label_map)} for m in messages]
            timeline += [{'time': a.created_on, 'type': 'A', 'item': a.as_json()} for a in actions]
            timeline = sorted(timeline, key=lambda event: event['time'])

            last_event_time = timeline[len(timeline) - 1]['time'] if timeline else None
            last_message_id = messages[len(messages) - 1].id if messages else None
            last_action_id = actions[len(actions) - 1].id if actions else None

            context['timeline'] = timeline
            context['last_event_time'] = last_event_time
            context['last_message_id'] = last_message_id
            context['last_action_id'] = last_action_id
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({'results': context['timeline'],
                                 'last_event_time': context['last_event_time'],
                                 'last_message_id': context['last_message_id'],
                                 'last_action_id': context['last_action_id']})


class GroupCRUDL(SmartCRUDL):
    model = Group
    actions = ('list', 'select')

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'contacts')
        default_order = ('name',)

        def derive_queryset(self, **kwargs):
            return Group.get_all(self.request.org)

        def get_contacts(self, obj):
            group_sizes = get_obj_cacheable(self, '_group_sizes',
                                            lambda: Group.fetch_sizes(self.request.org, self.derive_queryset()))
            return group_sizes[obj]

    class Select(OrgPermsMixin, SmartFormView):
        class GroupsForm(forms.Form):
            groups = forms.MultipleChoiceField(choices=(), label=_("Groups"),
                                               help_text=_("Contact groups to be used as filter groups."))

            def __init__(self, *args, **kwargs):
                org = kwargs['org']
                del kwargs['org']
                super(GroupCRUDL.Select.GroupsForm, self).__init__(*args, **kwargs)

                choices = []
                for group in org.get_temba_client().get_groups():
                    choices.append((group.uuid, "%s (%d)" % (group.name, group.size)))

                self.fields['groups'].choices = choices
                self.fields['groups'].initial = [group.uuid for group in Group.get_all(org)]

        title = _("Filter Groups")
        form_class = GroupsForm
        success_url = '@cases.group_list'
        submit_button_name = _("Update")
        success_message = _("Updated contact groups to use as filter groups")

        def get_form_kwargs(self):
            kwargs = super(GroupCRUDL.Select, self).get_form_kwargs()
            kwargs['org'] = self.request.user.get_org()
            return kwargs

        def form_valid(self, form):
            Group.update_groups(self.request.org, form.cleaned_data['groups'])
            return HttpResponseRedirect(self.get_success_url())


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

    def clean_keywords(self):
        return ','.join(parse_csv(self.cleaned_data['keywords']))

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

    class Delete(OrgObjPermsMixin, SmartDeleteView):
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


class MessageSearchMixin(object):
    def derive_search(self):
        """
        Collects and prepares message search parameters into JSON serializable dict
        """
        request = self.request

        labels = Label.get_all(request.org, request.user)
        label_id = request.GET.get('label', None)
        if label_id:
            labels = labels.filter(pk=label_id)
        labels = [l.name for l in labels]

        contact = request.GET.get('contact', None)
        contacts = [contact] if contact else None

        groups = request.GET.get('groups', None)
        groups = parse_csv(groups) if groups else None

        return {'labels': labels,
                'contacts': contacts,
                'groups': groups,
                'after': parse_iso8601(request.GET.get('after', None)),
                'before': parse_iso8601(request.GET.get('before', None)),
                'text': request.GET.get('text', None)}


class MessageSearchView(OrgPermsMixin, MessageSearchMixin, SmartTemplateView):
    """
    JSON endpoint for fetching messages
    """
    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(MessageSearchView, self).get_context_data(**kwargs)

        search = self.derive_search()
        page = int(self.request.GET.get('page', 0))

        client = self.request.org.get_temba_client()
        pager = client.pager(start_page=page) if page else None
        messages = client.get_messages(pager=pager, labels=search['labels'],
                                       contacts=search['contacts'], groups=search['groups'],
                                       direction='I', _types=['I'], statuses=['H'],
                                       after=search['after'], before=search['before'],
                                       text=search['text'])

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

        results = [Message.as_json(m, label_map) for m in context['messages']]

        return JsonResponse({'results': results, 'has_more': context['has_more'], 'total': context['total']})


class MessageActionView(OrgPermsMixin, View):
    """
    AJAX endpoint for bulk message actions. Takes a list of message ids.
    """
    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def post(self, request, *args, **kwargs):
        org = self.request.org
        user = self.request.user

        action = kwargs['action']
        message_ids = parse_csv(self.request.POST.get('messages', ''), as_ints=True)
        label_id = int(self.request.POST.get('label', 0))
        label = Label.get_all(org, user).get(pk=label_id) if label_id else None

        if action == 'flag':
            Message.bulk_flag(org, user, message_ids)
        elif action == 'unflag':
            Message.bulk_unflag(org, user, message_ids)
        elif action == 'label':
            Message.bulk_label(org, user, message_ids, label)
        elif action == 'archive':
            Message.bulk_archive(org, user, message_ids)
        else:
            return HttpResponseBadRequest("Invalid action: %s", action)

        return HttpResponse(status=204)


class MessageSendView(OrgPermsMixin, View):
    """
    JSON endpoint for message sending. Takes a list of contact UUIDs or URNs
    """
    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def post(self, request, *args, **kwargs):
        urns = parse_csv(request.POST.get('urns', ''), as_ints=False)
        contacts = parse_csv(request.POST.get('contacts', ''), as_ints=False)
        text = request.POST['text']

        client = request.org.get_temba_client()
        broadcast = client.create_broadcast(urns=urns, contacts=contacts, text=text)

        return JsonResponse({'broadcast_id': broadcast.id})


class MessageExportCRUDL(SmartCRUDL):
    model = MessageExport
    actions = ('create', 'read')

    class Create(OrgPermsMixin, MessageSearchMixin, SmartCreateView):
        def post(self, request, *args, **kwargs):

            search = self.derive_search()
            export = MessageExport.create(self.request.org, self.request.user, search)

            message_export.delay(export.pk)

            return JsonResponse({'export_id': export.pk})

    class Read(OrgObjPermsMixin, SmartReadView):
        """
        Download view for message exports
        """
        title = _("Download Messages")

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'%s/download/(?P<pk>\d+)/' % path

        def get(self, request, *args, **kwargs):
            if 'download' in request.GET:
                export = self.get_object()

                export_file = default_storage.open(export.filename, 'rb')
                user_filename = 'message_export.xls'

                response = HttpResponse(export_file, content_type='application/vnd.ms-excel')
                response['Content-Disposition'] = 'attachment; filename=%s' % user_filename

                return response
            else:
                return super(MessageExportCRUDL.Read, self).get(request, *args, **kwargs)

        def get_context_data(self, **kwargs):
            context = super(MessageExportCRUDL.Read, self).get_context_data(**kwargs)
            context['download_url'] = '%s?download=1' % reverse('cases.messageexport_read', args=[self.object.pk])
            return context


class PartnerForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')
        super(PartnerForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Partner
        fields = ('name',)


class PartnerFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(PartnerFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.user.get_org()
        return kwargs


class PartnerCRUDL(SmartCRUDL):
    actions = ('create', 'read', 'update', 'list')
    model = Partner

    class Create(OrgPermsMixin, PartnerFormMixin, SmartCreateView):
        form_class = PartnerForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            self.object = Partner.create(org, data['name'])

    class Update(OrgObjPermsMixin, PartnerFormMixin, SmartUpdateView):
        form_class = PartnerForm

    class Read(OrgObjPermsMixin, SmartReadView):
        def get_context_data(self, **kwargs):
            context = super(PartnerCRUDL.Read, self).get_context_data(**kwargs)
            context['labels'] = self.object.get_labels()
            context['managers'] = self.object.get_managers()
            context['analysts'] = self.object.get_analysts()
            return context

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'labels')
        default_order = ('name',)

        def derive_queryset(self, **kwargs):
            qs = super(PartnerCRUDL.List, self).derive_queryset(**kwargs)
            qs = qs.filter(org=self.request.org)
            return qs

        def get_labels(self, obj):
            return ", ".join([l.name for l in obj.get_labels()])


class HomeDataMixin(object):
    """
    Mixin to add site metadata to the context in JSON format which can then used
    """
    def get_context_data(self, **kwargs):
        context = super(HomeDataMixin, self).get_context_data(**kwargs)
        org = self.request.org
        user = self.request.user
        partner = user.get_partner()

        labels = Label.get_all(org, user).order_by('name')
        partners = Partner.get_all(org).order_by('name')
        groups = Group.get_all(org).order_by('name')

        # annotate labels with counts
        self.annotate_labels(labels)

        # angular app requires context data in JSON format
        context['context_data_json'] = json_encode({
            'user': {'id': user.pk, 'partner': partner.as_json() if partner else None},
            'partners': [p.as_json() for p in partners],
            'labels': [l.as_json() for l in labels],
            'groups': [g.as_json() for g in groups],
        })

        return context


class InboxView(OrgPermsMixin, HomeDataMixin, SmartTemplateView):
    """
    Inbox view
    """
    template_name = 'cases/home_inbox.haml'

    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def annotate_labels(self, labels):
        for label, count in Label.get_message_counts(self.request.org, labels).iteritems():
            label.count = count


class CasesView(OrgPermsMixin, HomeDataMixin, SmartTemplateView):
    """
    Open or closed cases views
    """

    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_template_names(self):
        case_status = self.kwargs['case_status']
        return ['cases/home_open.haml'] if case_status == 'open' else ['cases/home_closed.haml']

    def annotate_labels(self, labels):
        closed = self.kwargs['case_status'] == 'closed'
        for label, count in Label.get_case_counts(labels, closed).iteritems():
            label.count = count

    def get_context_data(self, **kwargs):
        context = super(CasesView, self).get_context_data(**kwargs)

        context['case_status'] = self.kwargs['case_status']

        return context
