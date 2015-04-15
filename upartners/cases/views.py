from __future__ import absolute_import, unicode_literals

import json

from dash.orgs.views import OrgPermsMixin
from django.http import HttpResponse, JsonResponse
from smartmin.users.views import SmartCRUDL, SmartListView, SmartCreateView, SmartReadView, SmartUpdateView
from temba.utils import parse_iso8601
from upartners.home.models import message_as_json
from upartners.labels.models import Label
from upartners.partners.models import Partner
from .models import Case


class CaseCRUDL(SmartCRUDL):
    model = Case
    actions = ('read', 'list', 'open', 'note', 'reassign', 'close', 'reopen', 'fetch', 'timeline')

    class Read(OrgPermsMixin, SmartReadView):
        fields = ()

        def derive_queryset(self, **kwargs):
            return Case.get_all(self.request.org)

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Read, self).get_context_data(**kwargs)

            partners = Partner.get_all(self.request.org).order_by('name')

            # angular app requires context data in JSON format
            context['context_data_json'] = json.dumps({
                'case': self.object.as_json(),
                'partners': [p.as_json() for p in partners],
            })

            return context

    class List(OrgPermsMixin, SmartListView):
        fields = ('id', 'labels', 'opened_on')
        default_order = ('-opened_on',)

        def derive_queryset(self, **kwargs):
            return Case.get_all(self.request.org)

        def get_id(self, obj):
            return '#%d' % obj.pk

        def get_labels(self, obj):
            return ', '.join([l.name for l in obj.labels.all()])

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

            case = Case.open(request.org, request.user, labels, assignee, message.contact, message.id, message.created_on)

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

    class Fetch(OrgPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching a single case
        """
        permission = 'cases.case_read'

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse(self.object.as_json())

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
            messages = [m for m in messages if m.id > since_message_id]

            # fetch actions
            actions = self.object.actions.select_related('assignee', 'created_by')
            if since_action_id:
                actions = actions.filter(pk__gt=since_action_id)

            label_map = {l.name: l for l in Label.get_all(self.request.org)}

            timeline = [{'time': m.created_on, 'type': 'M', 'item': message_as_json(m, label_map)} for m in messages]
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
