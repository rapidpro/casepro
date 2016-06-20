from __future__ import unicode_literals

import six

from collections import defaultdict
from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.core.urlresolvers import reverse
from django.utils.timesince import timesince
from django.utils.translation import ugettext_lazy as _
from el_pagination.paginators import LazyPaginator
from smartmin.mixins import NonAtomicMixin
from smartmin.views import SmartCRUDL, SmartTemplateView
from smartmin.views import SmartListView, SmartCreateView, SmartReadView, SmartUpdateView, SmartDeleteView
from temba_client.utils import parse_iso8601

from casepro.rules.mixins import RuleFormMixin
from casepro.statistics.models import DailyCount
from casepro.utils import parse_csv, str_to_bool, JSONEncoder, json_encode, month_range
from casepro.utils.export import BaseDownloadView

from .forms import LabelForm, FaqForm
from .models import Label, FAQ, Message, MessageExport, MessageFolder, Outgoing, OutgoingFolder, ReplyExport
from .tasks import message_export, reply_export


RESPONSE_DELAY_WARN_SECONDS = 24 * 60 * 60  # show response delays > 1 day as warning


class LabelCRUDL(SmartCRUDL):
    actions = ('create', 'update', 'read', 'delete', 'list', 'watch', 'unwatch')
    model = Label

    class Create(RuleFormMixin, OrgPermsMixin, SmartCreateView):
        form_class = LabelForm

        def get_form_kwargs(self):
            kwargs = super(LabelCRUDL.Create, self).get_form_kwargs()
            kwargs['org'] = self.request.org
            kwargs['is_create'] = True
            return kwargs

        def derive_initial(self):
            # label created manually in casepro aren't synced by default
            initial = super(LabelCRUDL.Create, self).derive_initial()
            initial['is_synced'] = False
            return initial

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.org
            name = data['name']
            description = data['description']
            tests = self.construct_tests()
            is_synced = data['is_synced']

            self.object = Label.create(org, name, description, tests, is_synced)

    class Update(RuleFormMixin, OrgObjPermsMixin, SmartUpdateView):
        form_class = LabelForm
        success_url = 'id@msgs.label_read'

        def get_form_kwargs(self):
            kwargs = super(LabelCRUDL.Update, self).get_form_kwargs()
            kwargs['org'] = self.request.org
            kwargs['is_create'] = False
            return kwargs

        def post_save(self, obj):
            obj = super(LabelCRUDL.Update, self).post_save(obj)

            tests = self.construct_tests()
            obj.update_tests(tests)

            return obj

    class Read(OrgObjPermsMixin, SmartReadView):
        def get_queryset(self):
            return Label.get_all(self.request.org, self.request.user)

        def get_context_data(self, **kwargs):
            context = super(LabelCRUDL.Read, self).get_context_data(**kwargs)

            # augment usual label JSON
            label_json = self.object.as_json()
            label_json['watching'] = self.object.is_watched_by(self.request.user)

            # angular app requires context data in JSON format
            context['context_data_json'] = json_encode({
                'label': label_json
            })
            context['summary'] = self.get_summary(self.object)
            return context

        def get_summary(self, label):
            return {
                'total_messages': DailyCount.get_by_label([label], DailyCount.TYPE_INCOMING).total()
            }

    class Delete(OrgObjPermsMixin, SmartDeleteView):
        cancel_url = '@msgs.label_list'

        def post(self, request, *args, **kwargs):
            label = self.get_object()
            label.release()
            return HttpResponse(status=204)

    class List(OrgPermsMixin, SmartListView):
        def get(self, request, *args, **kwargs):
            with_activity = str_to_bool(self.request.GET.get('with_activity', ''))
            labels = Label.get_all(self.request.org, self.request.user).order_by('name')

            if with_activity:
                # get message statistics
                this_month = DailyCount.get_by_label(labels, DailyCount.TYPE_INCOMING, *month_range(0)).scope_totals()
                last_month = DailyCount.get_by_label(labels, DailyCount.TYPE_INCOMING, *month_range(-1)).scope_totals()

            def as_json(label):
                obj = label.as_json()
                if with_activity:
                    obj['messages'] = {
                        'this_month': this_month.get(label, 0),
                        'last_month': last_month.get(label, 0),
                    }
                return obj

            return JsonResponse({'results': [as_json(l) for l in labels]})

    class Watch(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for watching a label
        """
        permission = 'msgs.label_read'

        def post(self, request, *args, **kwargs):
            self.get_object().watch(request.user)
            return HttpResponse(status=204)

    class Unwatch(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for unwatching a label
        """
        permission = 'msgs.label_read'

        def post(self, request, *args, **kwargs):
            self.get_object().unwatch(request.user)
            return HttpResponse(status=204)


class FaqCRUDL(SmartCRUDL):
    model = FAQ
    actions = ('list', 'create', 'read', 'update', 'delete')

    class List(OrgPermsMixin, SmartListView):
        fields = ('question', 'answer')
        default_order = ('question',)

    class Create(OrgPermsMixin, SmartCreateView):
        form_class = FaqForm

        def get_form_kwargs(self):
            kwargs = super(FaqCRUDL.Create, self).get_form_kwargs()
            return kwargs

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.org
            question = data['question']
            answer = data['answer']

            # labels = data['labels']  # continue here on monday!
            labels = Label.objects.all()

            faq = FAQ.objects.create(org=org, question=question, answer=answer)
            faq.labels.add(*labels)
            self.object = faq

    class Read(OrgPermsMixin, SmartReadView):

        def get_queryset(self):
            return FAQ.objects.all()

        def get_context_data(self, **kwargs):
            context = super(FaqCRUDL.Read, self).get_context_data(**kwargs)
            edit_button_url = reverse('msgs.faq_update', args=[self.object.pk])
            context['context_data_json'] = json_encode({'faq': self.object.as_json()})
            context['edit_button_url'] = edit_button_url
            context['can_delete'] = True
            return context

    class Update(OrgPermsMixin, SmartUpdateView):
        form_class = FaqForm

    class Delete(OrgPermsMixin, SmartDeleteView):
        cancel_url = '@msgs.faq_list'

        def post(self, request, *args, **kwargs):
            faq = self.get_object()
            faq.delete()

            return HttpResponse(status=204)


class MessageSearchMixin(object):
    def derive_search(self):
        """
        Collects and prepares message search parameters into JSON serializable dict
        """
        folder = MessageFolder[self.request.GET['folder']]
        label_id = self.request.GET.get('label', None)
        include_archived = str_to_bool(self.request.GET.get('archived', ''))
        text = self.request.GET.get('text', None)
        contact_id = self.request.GET.get('contact', None)
        group_ids = parse_csv(self.request.GET.get('groups', ''), as_ints=True)
        after = parse_iso8601(self.request.GET.get('after', None))
        before = parse_iso8601(self.request.GET.get('before', None))

        return {
            'folder': folder,
            'label': label_id,
            'include_archived': include_archived,  # only applies to flagged folder
            'text': text,
            'contact': contact_id,
            'groups': group_ids,
            'after': after,
            'before': before
        }


class MessageCRUDL(SmartCRUDL):
    actions = ('search', 'action', 'label', 'bulk_reply', 'forward', 'history')
    model = Message

    class Search(OrgPermsMixin, MessageSearchMixin, SmartTemplateView):
        """
        JSON endpoint for fetching incoming messages
        """
        def get_context_data(self, **kwargs):
            context = super(MessageCRUDL.Search, self).get_context_data(**kwargs)

            org = self.request.org
            user = self.request.user
            page = int(self.request.GET.get('page', 1))

            search = self.derive_search()
            messages = Message.search(org, user, search)
            paginator = LazyPaginator(messages, per_page=50)

            context['object_list'] = paginator.page(page)
            context['has_more'] = paginator.num_pages > page
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({
                'results': [m.as_json() for m in context['object_list']],
                'has_more': context['has_more']
            }, encoder=JSONEncoder)

    class Action(OrgPermsMixin, SmartTemplateView):
        """
        AJAX endpoint for bulk message actions. Takes a list of message ids.
        """
        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'^message/action/(?P<action>\w+)/$'

        def post(self, request, *args, **kwargs):
            org = request.org
            user = request.user

            action = kwargs['action']

            message_ids = request.json['messages']
            messages = org.incoming_messages.filter(org=org, backend_id__in=message_ids)

            label_id = request.json.get('label')
            label = Label.get_all(org, user).get(pk=label_id) if label_id else None

            if action == 'flag':
                Message.bulk_flag(org, user, messages)
            elif action == 'unflag':
                Message.bulk_unflag(org, user, messages)
            elif action == 'label':
                Message.bulk_label(org, user, messages, label)
            elif action == 'unlabel':
                Message.bulk_unlabel(org, user, messages, label)
            elif action == 'archive':
                Message.bulk_archive(org, user, messages)
            elif action == 'restore':
                Message.bulk_restore(org, user, messages)
            else:  # pragma: no cover
                return HttpResponseBadRequest("Invalid action: %s", action)

            return HttpResponse(status=204)

    class Label(OrgPermsMixin, SmartTemplateView):
        """
        AJAX endpoint for labelling a message.
        """
        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'^message/label/(?P<id>\d+)/$'

        def post(self, request, *args, **kwargs):
            org = request.org
            user = request.user
            user_labels = Label.get_all(self.org, user)

            message_id = int(kwargs['id'])
            message = org.incoming_messages.filter(org=org, backend_id=message_id).first()

            label_ids = request.json['labels']
            specified_labels = list(user_labels.filter(pk__in=label_ids))

            # user can't remove labels that they can't see
            unseen_labels = [l for l in message.labels.all() if l not in user_labels]

            message.update_labels(user, specified_labels + unseen_labels)

            return HttpResponse(status=204)

    class BulkReply(OrgPermsMixin, SmartTemplateView):
        """
        JSON endpoint for bulk messages replies
        """
        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'^message/bulk_reply/$'

        def post(self, request, *args, **kwargs):
            text = request.json['text']
            message_ids = request.json['messages']
            messages = Message.objects.filter(org=request.org, backend_id__in=message_ids).select_related('contact')

            # organize messages by contact
            messages_by_contact = defaultdict(list)
            for msg in messages:
                messages_by_contact[msg.contact].append(msg)

            # the actual message that will be replied to is the oldest selected message for each contact
            reply_tos = []
            for contact, contact_messages in six.iteritems(messages_by_contact):
                contact_messages = sorted(contact_messages, key=lambda m: m.created_on, reverse=True)
                reply_tos.append(contact_messages[0])

            outgoing = Outgoing.create_bulk_replies(request.org, request.user, text, reply_tos)
            return JsonResponse({'messages': len(outgoing)})

    class Forward(OrgPermsMixin, SmartTemplateView):
        """
        JSON endpoint for forwarding a message to a URN
        """
        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'^message/forward/(?P<id>\d+)/$'

        def post(self, request, *args, **kwargs):
            text = request.json['text']
            message = Message.objects.get(org=request.org, backend_id=int(kwargs['id']))
            urns = request.json['urns']

            outgoing = Outgoing.create_forwards(request.org, request.user, text, urns, message)
            return JsonResponse({'messages': len(outgoing)})

    class History(OrgPermsMixin, SmartTemplateView):
        """
        JSON endpoint for fetching message history. Takes a message backend id
        """
        @classmethod
        def derive_url_pattern(cls, path, action):
            return r'^message/history/(?P<id>\d+)/$'

        def get(self, request, *args, **kwargs):
            message = Message.objects.get(org=request.org, backend_id=int(kwargs['id']))
            actions = [a.as_json() for a in message.get_history()]
            return JsonResponse({'actions': actions}, encoder=JSONEncoder)


class MessageExportCRUDL(SmartCRUDL):
    model = MessageExport
    actions = ('create', 'read')

    class Create(NonAtomicMixin, OrgPermsMixin, MessageSearchMixin, SmartCreateView):
        def post(self, request, *args, **kwargs):
            search = self.derive_search()
            export = MessageExport.create(self.request.org, self.request.user, search)

            message_export.delay(export.pk)

            return JsonResponse({'export_id': export.pk})

    class Read(BaseDownloadView):
        title = _("Download Messages")
        filename = 'message_export.xls'


class ReplySearchMixin(object):
    def derive_search(self):
        """
        Collects and prepares reply search parameters into JSON serializable dict
        """
        params = self.request.GET
        partner = params.get('partner')
        after = parse_iso8601(params.get('after'))
        before = parse_iso8601(params.get('before'))

        return {'partner': partner, 'after': after, 'before': before}


class OutgoingCRUDL(SmartCRUDL):
    actions = ('search', 'search_replies')
    model = Outgoing

    class Search(OrgPermsMixin, SmartTemplateView):
        """
        JSON endpoint for fetching outgoing messages
        """
        def derive_search(self):
            folder = OutgoingFolder[self.request.GET['folder']]
            text = self.request.GET.get('text', None)
            contact = self.request.GET.get('contact', None)

            return {'folder': folder, 'text': text, 'contact': contact}

        def get_context_data(self, **kwargs):
            context = super(OutgoingCRUDL.Search, self).get_context_data(**kwargs)

            org = self.request.org
            user = self.request.user
            page = int(self.request.GET.get('page', 1))

            search = self.derive_search()
            messages = Outgoing.search(org, user, search)
            paginator = LazyPaginator(messages, per_page=50)

            context['object_list'] = paginator.page(page)
            context['has_more'] = paginator.num_pages > page
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({
                'results': [m.as_json() for m in context['object_list']],
                'has_more': context['has_more']
            }, encoder=JSONEncoder)

    class SearchReplies(OrgPermsMixin, ReplySearchMixin, SmartTemplateView):
        """
        JSON endpoint to fetch replies made by users
        """
        def get(self, request, *args, **kwargs):
            org = self.request.org
            user = self.request.user
            page = int(self.request.GET.get('page', 1))

            search = self.derive_search()
            items = Outgoing.search_replies(org, user, search)

            paginator = LazyPaginator(items, 50)
            outgoing = paginator.page(page)
            has_more = paginator.num_pages > page

            def as_json(msg):
                delay = (msg.created_on - msg.reply_to.created_on).total_seconds()
                obj = msg.as_json()
                obj.update({
                    'reply_to': {
                        'text': msg.reply_to.text,
                        'flagged': msg.reply_to.is_flagged,
                        'labels': [l.as_json(full=False) for l in msg.reply_to.labels.all()],
                    },
                    'response': {
                        'delay': timesince(msg.reply_to.created_on, now=msg.created_on),
                        'warning': delay > RESPONSE_DELAY_WARN_SECONDS
                    }
                })
                return obj

            return JsonResponse({'results': [as_json(o) for o in outgoing], 'has_more': has_more}, encoder=JSONEncoder)


class ReplyExportCRUDL(SmartCRUDL):
    model = ReplyExport
    actions = ('create', 'read')

    class Create(NonAtomicMixin, OrgPermsMixin, ReplySearchMixin, SmartCreateView):
        def post(self, request, *args, **kwargs):
            search = self.derive_search()
            export = self.model.create(self.request.org, self.request.user, search)

            reply_export.delay(export.pk)

            return JsonResponse({'export_id': export.pk})

    class Read(BaseDownloadView):
        title = _("Download Replies")
        filename = 'reply_export.xls'
