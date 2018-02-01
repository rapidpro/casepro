from __future__ import unicode_literals

import regex

from django import forms
from django.utils.translation import ugettext_lazy as _

from casepro.contacts.models import Group
from casepro.rules.forms import FieldTestField
from casepro.rules.models import ContainsTest
from casepro.utils import parse_csv, normalize, is_valid_language_code

from .models import Label, FAQ


class LabelForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)

    description = forms.CharField(label=_("Description"), max_length=255, widget=forms.Textarea)

    is_synced = forms.BooleanField(
        label=_("Is synced"), required=False,
        help_text=_("Whether label should be kept synced with backend")
    )

    keywords = forms.CharField(
        label=_("Keywords"), widget=forms.Textarea, required=False,
        help_text=_("Match messages containing any of these words (comma separated)")
    )

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(), label=_("Groups"), required=False,
        help_text=_("Match messages from these groups (select none to include all groups)")
    )

    field_test = forms.CharField()  # switched below in __init__

    ignore_single_words = forms.BooleanField(
        label=_("Ignore single words"), required=False,
        help_text=_("Whether to ignore messages consisting of a single word")
    )

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')
        is_create = kwargs.pop('is_create')

        super(LabelForm, self).__init__(*args, **kwargs)

        # don't let users change names of existing labels
        if not is_create:
            self.fields['name'].widget = forms.TextInput(attrs={'readonly': 'readonly'})

        self.fields['groups'].queryset = Group.get_all(org).order_by('name')

        self.fields['field_test'] = FieldTestField(
            org=org, label=_("Field criteria"), required=False,
            help_text=_("Match messages where contact field value is equal to any of these values (comma separated)")
        )

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if name.lower() == 'flagged':
            raise forms.ValidationError(_("Reserved label name"))

        elif len(name) > Label.MAX_NAME_LEN:
            raise forms.ValidationError(_("Label name must be %d characters or less") % Label.MAX_NAME_LEN)

        # first character must be a word char
        elif not regex.match('\w', name[0], flags=regex.UNICODE):
            raise forms.ValidationError(_("Label name must start with a letter or digit"))
        return name

    def clean_keywords(self):
        keywords = parse_csv(self.cleaned_data['keywords'])
        clean_keywords = []
        for keyword in keywords:
            clean_keyword = normalize(keyword)

            if not ContainsTest.is_valid_keyword(keyword):
                raise forms.ValidationError(_("Invalid keyword: %s") % keyword)

            clean_keywords.append(clean_keyword)

        return ', '.join(clean_keywords)

    class Meta:
        model = Label
        fields = ('name', 'description', 'is_synced', 'keywords', 'groups', 'field_test', 'ignore_single_words')


class FaqForm(forms.ModelForm):

    question = forms.CharField(label=_("Question"), max_length=255, widget=forms.Textarea)
    answer = forms.CharField(label=_("Answer"), max_length=480, widget=forms.Textarea)
    language = forms.CharField(label=_("Language"), max_length=3)
    # limit the parent choices to FAQs that have a ForeignKey parent that is None
    parent = forms.ModelChoiceField(queryset=FAQ.objects.filter(parent=None), required=False)
    labels = forms.ModelMultipleChoiceField(queryset=Label.objects.filter(), required=False, help_text=_(
        "If a Parent is selected, the labels will be copied from the Parent FAQ"))

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')

        super(FaqForm, self).__init__(*args, **kwargs)

        self.fields['parent'].queryset = FAQ.get_all(org)
        self.fields['labels'].queryset = Label.get_all(org)

    def clean_language(self):
        language = self.cleaned_data['language'].strip()
        if not is_valid_language_code(language):
            raise forms.ValidationError(_("Language must be valid a ISO-639-3 code"))
        return language

    def clean_labels(self):
        if 'labels' in self.cleaned_data and len(self.cleaned_data['labels']) != 0:
            labels = self.cleaned_data['labels']
        else:
            labels = None

        if 'parent' in self.cleaned_data and self.cleaned_data['parent']:
            parent = self.cleaned_data['parent']
            labels = None
        else:
            parent = None

        if parent is None and labels is None:
            raise forms.ValidationError(_("Labels are required if no Parent is selected"))

        return labels

    class Meta:
        model = FAQ
        fields = ('question', 'answer', 'language', 'parent', 'labels')
