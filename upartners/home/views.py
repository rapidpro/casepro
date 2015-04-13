from __future__ import absolute_import, unicode_literals

import json

from dash.orgs.views import OrgPermsMixin
from dash.utils import get_obj_cacheable
from django.http import HttpResponse, JsonResponse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from smartmin.users.views import SmartTemplateView
from temba.utils import parse_iso8601
from upartners.cases.models import Case
from upartners.groups.models import Group
from upartners.labels.models import Label, message_as_json
from upartners.partners.models import Partner


SYSTEM_LABEL_FLAGGED = "Flagged"


def parse_csv(csv, as_ints=False):
    """
    Parses a comma separated list of values as strings or integers
    """
    items = []
    for val in csv.split(','):
        items.append(int(val) if as_ints else val.strip())
    return items


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
    title = _("Inbox")
    template_name = 'home/home_inbox.haml'

    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(InboxView, self).get_context_data(**kwargs)
        user = self.request.user

        # TODO move this to middleware ?
        self.request.partner = user.profile.partner if user.has_profile() else None

        labels = Label.get_all(self.request.org)
        partners = Partner.get_all(self.request.org)
        groups = Group.get_all(self.request.org)

        context['initial_label_id'] = self.kwargs.get('label_id', None)
        #context['inbox_count'] = self.object.get_count()
        #context['open_count'] = Case.get_open(self.request.org, self.object).count()
        #context['closed_count'] = Case.get_closed(self.request.org, self.object).count()

        # TODO figure out how to initialize the group select2 options with angular and remove this
        context['groups'] = groups

        # angular app requires context data in JSON format
        context['context_data_json'] = json.dumps(dict(
            labels=[dict(id=l.pk, name=l.name) for l in labels],
            partners=[dict(id=p.pk, name=p.name) for p in partners],
            groups=[dict(id=g.pk, name=g.name) for g in groups],
        ))

        return context


class MessagesView(OrgPermsMixin, SmartTemplateView):
    """
    JSON endpoint for fetching messages
    """
    def has_permission(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def get_context_data(self, **kwargs):
        context = super(MessagesView, self).get_context_data(**kwargs)

        page = int(self.request.GET.get('page', 1))

        label_id = self.request.GET.get('label', None)
        if label_id:
            labels = [Label.get_all(self.request.org).get(pk=label_id)]
        else:
            labels = Label.get_all(self.request.org)

        text = self.request.GET.get('text', None)
        after = parse_iso8601(self.request.GET.get('after', None))
        before = parse_iso8601(self.request.GET.get('before', None))

        group_uuids = self.request.GET.get('groups', None)
        group_uuids = parse_csv(group_uuids) if group_uuids else None

        reverse = self.request.GET.get('reverse', 'false')

        client = self.request.org.get_temba_client()
        pager = client.pager(start_page=page)
        messages = client.get_messages(pager=pager, labels=[l.name for l in labels], direction='I',
                                       after=after, before=before, groups=group_uuids, text=text, reverse=reverse)

        context['page'] = page
        context['has_more'] = pager.has_more()
        context['total'] = pager.total
        context['messages'] = messages
        return context

    def render_to_response(self, context, **response_kwargs):
        include_labels = {l.name for l in Label.get_all(self.request.org)}
        results = [message_as_json(m, include_labels) for m in context['messages']]

        return JsonResponse({'page': context['page'],
                             'has_more': context['has_more'],
                             'total': context['total'],
                             'results': results})


class MessageActions(View):
    actions = ('flag', 'unflag', 'label', 'archive')

    @classmethod
    def get_url_pattern(cls):
        return r'^messages/(?P<action>%s)/$' % '|'.join(cls.actions)

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

        return HttpResponse(status=204)