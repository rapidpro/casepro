from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from django import forms
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from smartmin.users.views import SmartCRUDL, SmartCreateView, SmartUpdateView, SmartReadView, SmartListView
from upartners.labels.models import Label, parse_keywords
from upartners.partners.models import Partner


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


class LabelCRUDL(SmartCRUDL):
    actions = ('create', 'read', 'update', 'list', 'messages')
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

    class Read(OrgObjPermsMixin, SmartReadView):
        fields = ('name', 'description')

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'description', 'partners')
        default_order = ('name',)

        def derive_queryset(self, **kwargs):
            qs = super(LabelCRUDL.List, self).derive_queryset(**kwargs)
            qs = qs.filter(org=self.request.org, is_active=True)
            return qs

        def get_partners(self, obj):
            return ', '.join([p.name for p in obj.get_partners()])

    class Messages(OrgPermsMixin, SmartReadView):
        permission = 'labels.label_read'

        def get_context_data(self, **kwargs):
            context = super(LabelCRUDL.Messages, self).get_context_data(**kwargs)

            page = int(self.request.GET.get('page', 1))

            client = self.request.org.get_temba_client()
            pager = client.pager(start_page=page)
            messages = client.get_messages(pager=pager, labels=[self.object.name], direction='I', _types=['I'])

            context['page'] = page
            context['has_more'] = pager.has_more()
            context['messages'] = messages
            return context

        def render_to_response(self, context, **response_kwargs):
            def render_msg(m):
                flagged = 'Flagged' in m.labels
                return {'id': m.id, 'text': m.text, 'time': m.created_on, 'flagged': flagged}

            results = [render_msg(msg) for msg in context['messages']]

            return JsonResponse({'page': context['page'], 'has_more': context['has_more'], 'results': results})


class MessageActions(View):
    actions = ('flag', 'unflag')

    @classmethod
    def get_url_pattern(cls):
        return r'^messages/(?P<action>%s)/$' % '|'.join(cls.actions)

    def post(self, request, *args, **kwargs):
        action = kwargs['action']
        message_ids = self.request.POST.get('message_ids', [])

        # TODO implement an endpoint in RapidPro that lets us label messages
        # client = self.request.org.get_temba_client()

        return HttpResponseBadRequest("Not yet implemented")
