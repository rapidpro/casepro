from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin
from django.http import HttpResponse, JsonResponse
from smartmin.users.views import SmartCRUDL, SmartListView, SmartCreateView, SmartReadView, SmartUpdateView
from temba.utils import parse_iso8601
from upartners.home.models import message_as_json
from upartners.labels.models import Label
from .models import Case


class CaseCRUDL(SmartCRUDL):
    model = Case
    actions = ('create', 'read', 'list', 'close', 'timeline')

    class Create(OrgPermsMixin, SmartCreateView):
        def derive_fields(self):
            fields = ['labels', 'contact_uuid', 'message_id', 'message_on']
            if not self.request.user.profile.partner:
                fields.append('assignee')
            return fields

        def save(self, obj):
            user = self.request.user
            labels = self.form.cleaned_data['labels']
            if user.profile.partner:
                partner = user.profile.partner
            else:
                partner = self.form.cleaned_data['partner']

            self.object = Case.open(self.request.org, user, labels, partner, obj.contact_uuid,
                                    obj.message_id, obj.message_on)

        # def render_to_response(self, context, **response_kwargs):
        #    return JsonResponse(dict(case_id=case.pk))

    class Read(OrgPermsMixin, SmartReadView):
        fields = ()

        def derive_queryset(self, **kwargs):
            return Case.get_all(self.request.org)

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Read, self).get_context_data(**kwargs)

            return context

    class List(OrgPermsMixin, SmartListView):
        fields = ('labels', 'contact_uuid', 'opened_on')
        default_order = ('-opened_on',)

        def derive_queryset(self, **kwargs):
            return Case.get_all(self.request.org)

        def get_labels(self, obj):
            return obj.labels.all()

    class Close(OrgPermsMixin, SmartUpdateView):
        permission = 'cases.case_update'

        def post(self, request, *args, **kwargs):
            case = self.get_object()
            case.close(self.request.user)
            return HttpResponse(status=204)

    class Timeline(OrgPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching case actions and messages
        """
        permission = 'cases.case_read'

        def get_context_data(self, **kwargs):
            context = super(CaseCRUDL.Timeline, self).get_context_data(**kwargs)
            org = self.request.org

            after = parse_iso8601(self.request.GET.get('after', self.object.message_on))

            # fetch messages
            before = self.object.closed_on
            messages = org.get_temba_client().get_messages(contacts=[self.object.contact_uuid],
                                                           after=after, before=before, reverse=True)

            # fetch actions
            actions = self.object.actions.select_related('assignee', 'created_by')
            if after:
                actions = actions.filter(created_on__gt=after)

            label_map = {l.name: l for l in Label.get_all(self.request.org)}

            timeline = [{'time': m.created_on, 'type': 'M', 'item': message_as_json(m, label_map)} for m in messages]
            timeline += [{'time': a.created_on, 'type': 'A', 'item': a.as_json()} for a in actions]
            timeline = sorted(timeline, key=lambda event: event['time'])

            context['timeline'] = timeline
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({'results': context['timeline']})
