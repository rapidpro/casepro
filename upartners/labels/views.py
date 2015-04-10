from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from dash.utils import intersection
from django import forms
from django.http import JsonResponse, HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from smartmin.users.views import SmartCRUDL, SmartCreateView, SmartUpdateView, SmartReadView, SmartListView
from temba.utils import parse_iso8601
from upartners.cases.models import Case
from upartners.groups.models import Group
from upartners.labels.models import Label, parse_keywords
from upartners.partners.models import Partner


SYSTEM_LABEL_FLAGGED = "Flagged"


def parse_ids_param(val):
    ids = []
    for id_str in val.split(','):
        ids.append(int(id_str))
    return ids


class LabelForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)

    description = forms.CharField(label=_("Description"), max_length=255, widget=forms.Textarea)

    keywords = forms.CharField(label=_("Keywords"), widget=forms.Textarea, required=False,
                               help_text=_("Match messages containing any of these words"))

    partners = forms.ModelMultipleChoiceField(label=_("Visible to"), queryset=Partner.objects.none())

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')

        super(LabelForm, self).__init__(*args, **kwargs)

        self.fields['partners'].queryset = Partner.get_all(org)

    def clean_keywords(self):
        return ','.join(parse_keywords(self.cleaned_data['keywords']))

    class Meta:
        model = Label
        fields = ('name', 'description', 'keywords', 'partners')


class LabelFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(LabelFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.user.get_org()
        return kwargs


class LabelReadView(OrgObjPermsMixin, SmartReadView):
    permission = 'labels.label_read'

    def get_context_data(self, **kwargs):
        context = super(LabelReadView, self).get_context_data(**kwargs)
        user = self.request.user

        # TODO move this to middleware
        self.request.partner = user.profile.partner if user.has_profile() else None

        partners = list(Partner.get_all(self.request.org))

        context['inbox_count'] = self.object.get_count()
        context['open_count'] = Case.get_open(self.request.org, self.object).count()
        context['closed_count'] = Case.get_closed(self.request.org, self.object).count()
        context['groups'] = Group.get_all(self.request.org)
        context['labels'] = Label.get_all(self.request.org)
        context['partners'] = partners

        return context


class LabelCRUDL(SmartCRUDL):
    actions = ('create', 'update', 'list', 'inbox', 'open', 'closed', 'messages', 'cases')
    model = Label

    class Create(OrgPermsMixin, LabelFormMixin, SmartCreateView):
        form_class = LabelForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            name = data['name']
            description = data['description']
            words = parse_keywords(data['keywords'])
            partners = data['partners']
            self.object = Label.create(org, name, description, words, partners)

    class Update(OrgObjPermsMixin, LabelFormMixin, SmartUpdateView):
        form_class = LabelForm

        def derive_initial(self):
            initial = super(LabelCRUDL.Update, self).derive_initial()
            initial['keywords'] = ', '.join(self.object.get_keywords())
            return initial

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'description', 'partners')
        default_order = ('name',)

        def derive_queryset(self, **kwargs):
            qs = super(LabelCRUDL.List, self).derive_queryset(**kwargs)
            qs = qs.filter(org=self.request.org, is_active=True)
            return qs

        def get_partners(self, obj):
            return ', '.join([p.name for p in obj.get_partners()])

    class Inbox(LabelReadView):
        """
        Shows all inbox messages with this label
        """
        pass

    class Open(LabelReadView):
        """
        Shows all open cases with this label
        """
        template_name = 'labels/label_cases.haml'

    class Closed(LabelReadView):
        """
        Shows all closed cases with this label
        """
        template_name = 'labels/label_cases.haml'

    class Messages(OrgPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching messages
        """
        permission = 'labels.label_read'

        def get_context_data(self, **kwargs):
            context = super(LabelCRUDL.Messages, self).get_context_data(**kwargs)

            page = int(self.request.GET.get('page', 1))
            text = self.request.GET.get('text', None)
            after = parse_iso8601(self.request.GET.get('after', None))
            before = parse_iso8601(self.request.GET.get('before', None))
            groups = self.request.GET.get('groups', None)
            reverse = self.request.GET.get('reverse', 'false')

            client = self.request.org.get_temba_client()
            pager = client.pager(start_page=page)
            messages = client.get_messages(pager=pager, labels=[self.object.name], direction='I', _types=['I'],
                                           after=after, before=before, groups=groups, text=text, reverse=reverse)

            context['page'] = page
            context['has_more'] = pager.has_more()
            context['total'] = pager.total
            context['messages'] = messages
            return context

        def render_to_response(self, context, **response_kwargs):
            display_labels = {l.name for l in Label.get_all(self.request.org) if l != self.object}

            def render_msg(m):
                flagged = 'Flagged' in m.labels
                labels = intersection(display_labels, m.labels)
                return {'id': m.id, 'text': m.text, 'contact': m.contact, 'time': m.created_on,
                        'labels': labels, 'flagged': flagged}

            results = [render_msg(msg) for msg in context['messages']]

            return JsonResponse({'page': context['page'],
                                 'has_more': context['has_more'],
                                 'total': context['total'],
                                 'results': results})

    class Cases(OrgPermsMixin, SmartReadView):
        """
        JSON endpoint for fetching cases
        """
        permission = 'labels.label_read'

        def get_context_data(self, **kwargs):
            context = super(LabelCRUDL.Cases, self).get_context_data(**kwargs)

            page = int(self.request.GET.get('page', 1))
            status = self.request.GET.get('status', 'open')

            # TODO

            context['page'] = 1
            context['has_more'] = False
            context['messages'] = []
            return context

        def render_to_response(self, context, **response_kwargs):
            def render_case(c):
                return {'id': c.id, 'text': c.text, 'time': c.opened_on}

            results = [render_case(case) for case in context['cases']]

            return JsonResponse({'page': context['page'], 'has_more': context['has_more'], 'results': results})


class MessageActions(View):
    actions = ('flag', 'unflag', 'label', 'archive')

    @classmethod
    def get_url_pattern(cls):
        return r'^messages/(?P<action>%s)/$' % '|'.join(cls.actions)

    def post(self, request, *args, **kwargs):
        action = kwargs['action']
        message_ids = parse_ids_param(self.request.POST.get('message_ids', ''))
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


class ContactActions(View):
    actions = ('send',)

    @classmethod
    def get_url_pattern(cls):
        return r'^contacts/(?P<action>%s)/$' % '|'.join(cls.actions)
