from __future__ import absolute_import, unicode_literals

import json

from dash.orgs.views import OrgPermsMixin
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from smartmin.users.views import SmartTemplateView
from temba.utils import parse_iso8601
from upartners.groups.models import Group
from upartners.labels.models import Label, SYSTEM_LABEL_FLAGGED
from upartners.partners.models import Partner
from .models import message_as_json, parse_csv, MessageExport
from .tasks import message_export


class HomeView(OrgPermsMixin, SmartTemplateView):
    """
    Homepage
    """
    title = _("Home")
    template_name = 'home/home.haml'

    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)

        labels = Label.get_all(self.request.org).order_by('name')

        # annotate each label with it's count
        for label, count in Label.fetch_counts(self.request.org, labels).iteritems():
            label.count = count

        context['labels'] = labels
        return context


class InboxView(OrgPermsMixin, SmartTemplateView):
    """
    Inbox view
    """
    template_name = 'home/home_inbox.haml'

    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(InboxView, self).get_context_data(**kwargs)
        user = self.request.user
        partner = user.get_partner()

        labels = (partner.labels if partner else Label.get_all(self.request.org)).order_by('name')
        partners = Partner.get_all(self.request.org).order_by('name')
        groups = Group.get_all(self.request.org).order_by('name')

        # annotate labels with their count
        for label, count in Label.fetch_counts(self.request.org, labels).iteritems():
            label.count = count

        context['initial_label_id'] = self.kwargs.get('label_id', None)

        # angular app requires context data in JSON format
        context['context_data_json'] = json.dumps({
            'user_partner': partner.as_json() if partner else None,
            'partners': [p.as_json() for p in partners],
            'labels': [l.as_json() for l in labels],
            'groups': [g.as_json() for g in groups],
        })

        return context


class CasesView(OrgPermsMixin, SmartTemplateView):
    """
    TODO
    """
    template_name = 'home/home_cases.haml'

    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(CasesView, self).get_context_data(**kwargs)
        user = self.request.user
        partner = user.get_partner()

        labels = (partner.labels if partner else Label.get_all(self.request.org)).order_by('name')
        partners = Partner.get_all(self.request.org).order_by('name')
        groups = Group.get_all(self.request.org).order_by('name')

        # annotate labels with their count
        for label, count in Label.fetch_counts(self.request.org, labels).iteritems():
            label.count = count

        context['initial_label_id'] = self.kwargs.get('label_id', None)

        # angular app requires context data in JSON format
        context['context_data_json'] = json.dumps({
            'user_partner': partner.as_json() if partner else None,
            'partners': [p.as_json() for p in partners],
            'labels': [l.as_json() for l in labels],
            'groups': [g.as_json() for g in groups],
        })

        return context


class MessageSearchMixin(object):
    def derive_search(self):
        """
        Collects and prepares message search parameters into JSON serializable dict
        """
        request = self.request

        label_id = request.GET.get('label', None)
        if label_id:
            labels = [Label.get_all(request.org).get(pk=label_id)]
        else:
            labels = Label.get_all(request.org)
        labels = [l.name for l in labels]

        text = request.GET.get('text', None)
        after = parse_iso8601(request.GET.get('after', None))
        before = parse_iso8601(request.GET.get('before', None))

        groups = request.GET.get('groups', None)
        groups = parse_csv(groups) if groups else None

        reverse = request.GET.get('reverse', 'false')

        return {'labels': labels, 'text': text, 'after': after, 'before': before, 'groups': groups, 'reverse': reverse}


class MessageFetchView(OrgPermsMixin, MessageSearchMixin, SmartTemplateView):
    """
    AJAX endpoint for fetching messages
    """
    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(MessageFetchView, self).get_context_data(**kwargs)

        search = self.derive_search()
        page = int(self.request.GET.get('page', 1))

        client = self.request.org.get_temba_client()
        pager = client.pager(start_page=page)
        messages = client.get_messages(pager=pager, labels=search['labels'], direction='I',
                                       after=search['after'], before=search['before'],
                                       groups=search['groups'], text=search['text'], reverse=search['reverse'])

        context['page'] = page
        context['has_more'] = pager.has_more()
        context['total'] = pager.total
        context['messages'] = messages
        return context

    def render_to_response(self, context, **response_kwargs):
        label_map = {l.name: l for l in Label.get_all(self.request.org)}

        results = [message_as_json(m, label_map) for m in context['messages']]

        return JsonResponse({'page': context['page'],
                             'has_more': context['has_more'],
                             'total': context['total'],
                             'results': results})


class MessageActionView(OrgPermsMixin, View):
    """
    AJAX endpoint for bulk message actions. Takes a list of message ids.
    """
    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def post(self, request, *args, **kwargs):
        action = kwargs['action']
        message_ids = parse_csv(self.request.POST.get('message_ids', ''), as_ints=True)
        label = self.request.POST.get('label', None)

        client = self.request.org.get_temba_client()

        if action == 'flag':
            client.label_messages(message_ids, label=SYSTEM_LABEL_FLAGGED)
        elif action == 'unflag':
            client.unlabel_messages(message_ids, label=SYSTEM_LABEL_FLAGGED)
        elif action == 'label':
            client.label_messages(message_ids, label=label)
        elif action == 'archive':
            client.archive_messages(message_ids)
        else:
            return HttpResponseBadRequest("Invalid action: %s", action)

        return HttpResponse(status=204)


class MessageSendView(OrgPermsMixin, View):
    """
    AJAX endpoint for message sending. Takes a list of contact UUIDs or URNs
    """
    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def post(self, request, *args, **kwargs):
        urns = parse_csv(self.request.POST.get('urns', ''), as_ints=False)
        contacts = parse_csv(self.request.POST.get('contacts', ''), as_ints=False)
        text = self.request.POST['text']

        client = self.request.org.get_temba_client()
        broadcast = client.create_broadcast(urns=urns, contacts=contacts, text=text)

        return JsonResponse({'broadcast_id': broadcast.id})


class MessageExportView(OrgPermsMixin, MessageSearchMixin, View):
    """
    AJAX endpoint for exporting a message search
    """
    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def post(self, request, *args, **kwargs):

        search = self.derive_search()
        export = MessageExport.create(self.request.org, self.request.user, search)

        message_export.delay(export.pk)

        return JsonResponse({'export_id': export.pk})
