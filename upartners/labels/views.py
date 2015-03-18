from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from django import forms
from django.utils.translation import ugettext_lazy as _
from smartmin.users.views import SmartCRUDL, SmartCreateView, SmartUpdateView, SmartReadView, SmartListView
from upartners.labels.models import Label, parse_words
from upartners.partners.models import Partner


class LabelForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)

    description = forms.CharField(label=_("Description"), max_length=255, widget=forms.Textarea)

    words = forms.CharField(label=_("Match words"), widget=forms.Textarea,
                            help_text=_("Match messages containing any of these words"))

    partners = forms.ModelMultipleChoiceField(label=_("Visible to"), queryset=Partner.objects.none())

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')

        super(LabelForm, self).__init__(*args, **kwargs)

        self.fields['partners'].queryset = Partner.get_all(org)

    def clean_words(self):
        return ','.join(parse_words(self.cleaned_data['words']))

    class Meta:
        model = Label
        fields = ('name', 'description', 'words', 'partners')


class LabelFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(LabelFormMixin, self).get_form_kwargs()
        kwargs['org'] = self.request.user.get_org()
        return kwargs


class LabelCRUDL(SmartCRUDL):
    actions = ('create', 'read', 'update', 'list')
    model = Label

    class Create(OrgPermsMixin, LabelFormMixin, SmartCreateView):
        form_class = LabelForm

        def save(self, obj):
            data = self.form.cleaned_data
            org = self.request.user.get_org()
            name = data['name']
            description = data['description']
            words = parse_words(data['words'])
            partners = data['partners']
            self.object = Label.create(org, name, description, words, partners)

    class Update(OrgObjPermsMixin, LabelFormMixin, SmartUpdateView):
        form_class = LabelForm

        def derive_initial(self):
            initial = super(LabelCRUDL.Update, self).derive_initial()
            initial['words'] = ', '.join(self.object.get_words())
            return initial

    class Read(OrgObjPermsMixin, SmartReadView):
        fields = ('name', 'description')

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'description', 'partners')

        def get_partners(self, obj):
            return ', '.join([p.name for p in obj.get_partners()])
