from __future__ import unicode_literals

from casepro.utils import parse_csv, str_to_bool
from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse
from django.db.transaction import non_atomic_requests
from django.http import HttpResponse, JsonResponse
from django.utils.translation import ugettext_lazy as _
from enum import Enum
from smartmin.views import SmartCRUDL, SmartCreateView, SmartReadView
from temba_client.utils import parse_iso8601
from .models import MessageExport, SYSTEM_LABEL_FLAGGED
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
