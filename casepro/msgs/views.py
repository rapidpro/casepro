from __future__ import unicode_literals

from casepro.cases.models import Case, Label
from casepro.utils import parse_csv, str_to_bool
from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse
from django.db.transaction import non_atomic_requests
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from enum import Enum
from smartmin.views import SmartCRUDL, SmartCreateView, SmartReadView, SmartTemplateView
from temba_client.utils import parse_iso8601
from .models import MessageExport, RemoteMessage, MessageAction, Outgoing, SYSTEM_LABEL_FLAGGED
from .tasks import message_export


class MessageView(Enum):
    inbox = 1
    flagged = 2
    archived = 3
    unlabelled = 4


class MessageSearchMixin(object):
    def derive_search(self):
        """
        Collects and prepares message search parameters into JSON serializable dict
        """
        from casepro.cases.models import Label

        request = self.request
        view = MessageView[request.GET['view']]
        after = parse_iso8601(request.GET.get('after', None))
        before = parse_iso8601(request.GET.get('before', None))

        label_objs = Label.get_all(request.org, request.user)

        if view == MessageView.unlabelled:
            labels = [('-%s' % l.name) for l in label_objs]
            msg_types = ['I']
        else:
            label_id = request.GET.get('label', None)
            if label_id:
                label_objs = label_objs.filter(pk=label_id)
            labels = [l.name for l in label_objs]
            msg_types = None

        if view == MessageView.flagged:
            labels.append('+%s' % SYSTEM_LABEL_FLAGGED)

        contact = request.GET.get('contact', None)
        contacts = [contact] if contact else None

        groups = request.GET.get('groups', None)
        groups = parse_csv(groups) if groups else None

        if view == MessageView.archived:
            archived = True  # only archived
        elif str_to_bool(request.GET.get('archived', '')):
            archived = None  # both archived and non-archived
        else:
            archived = False  # only non-archived

        return {'labels': labels,
                'contacts': contacts,
                'groups': groups,
                'after': after,
                'before': before,
                'text': request.GET.get('text', None),
                'types': msg_types,
                'archived': archived}


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


class MessageExportCRUDL(SmartCRUDL):
    model = MessageExport
    actions = ('create', 'read')

    class Create(OrgPermsMixin, MessageSearchMixin, SmartCreateView):
        @non_atomic_requests
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
            context['download_url'] = '%s?download=1' % reverse('msgs.messageexport_read', args=[self.object.pk])
            return context
