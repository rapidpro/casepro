from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _

from casepro.contacts.models import Group
from casepro.rules.forms import FieldTestField
from casepro.utils import parse_csv, normalize, normalize_language_code

from .models import Label, Language, FAQ


class LabelForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)
    description = forms.CharField(label=_("Description"), max_length=255, widget=forms.Textarea)
    keywords = forms.CharField(
        label=_("Keywords"), widget=forms.Textarea, required=False,
        help_text=_("Match messages containing any of these words (comma separated)")
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(), label=_("Groups"), required=False,
        help_text=_("Match messages from these groups (select none to include all groups)")
    )
    field_test = forms.CharField()  # switched below in __init__
    is_synced = forms.BooleanField(
        label=_("Is synced"), required=False,
        help_text=_("Whether label should be kept synced with backend")
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
        elif name.startswith('+') or name.startswith('-'):
            raise forms.ValidationError(_("Label name cannot start with + or -"))
        return name

    def clean_keywords(self):
        from casepro.rules.models import ContainsTest

        keywords = parse_csv(self.cleaned_data['keywords'])
        clean_keywords = []
        for keyword in keywords:
            clean_keyword = normalize(keyword)

            if len(keyword) < ContainsTest.KEYWORD_MIN_LENGTH:
                raise forms.ValidationError(_("Keywords must be at least %d characters long")
                                            % ContainsTest.KEYWORD_MIN_LENGTH)

            if not ContainsTest.is_valid_keyword(keyword):
                raise forms.ValidationError(_("Invalid keyword: %s") % keyword)

            clean_keywords.append(clean_keyword)

        return ', '.join(clean_keywords)

    class Meta:
        model = Label
        fields = ('name', 'description', 'keywords', 'groups', 'field_test', 'is_synced')


class LanguageForm(forms.ModelForm):

    code = forms.CharField(label=_("Code"), max_length=6,
                           widget=forms.TextInput(attrs={'placeholder': 'eng_UK'}))
    name = forms.CharField(label=_("Name"), max_length=100, required=False,
                           widget=forms.TextInput(attrs={'placeholder': 'English'}))
    location = forms.CharField(label=_("Location"), max_length=100, required=False,
                               widget=forms.TextInput(attrs={'placeholder': 'United Kingdom'}))

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        normalized_code = normalize(code)

        if len(normalized_code) != 6:
            raise forms.ValidationError(_("Language codes should be 6 characters long"))

        if normalized_code[3] != normalize('_'):
            raise forms.ValidationError(_("Language name and location should be seperated by an underscore"))

        return normalize_language_code(normalized_code)

    class Meta:
        model = Language
        fields = ('code', 'name', 'location')


class FaqForm(forms.ModelForm):

    question = forms.CharField(label=_("Question"), max_length=140)
    answer = forms.CharField(label=_("Answer"), max_length=140)
    language = forms.ModelChoiceField(queryset=Language.objects.filter())
    # limit the parent choices to FAQs that have a ForeignKey parent that is None
    parent = forms.ModelChoiceField(queryset=FAQ.objects.filter(parent=None), required=False)
    labels = forms.ModelMultipleChoiceField(queryset=Label.objects.filter(), required=False, help_text=_(
        "If a Parent is selected, the labels will be copied from the Parent FAQ"))

    def clean_labels(self):
        if 'labels' in self.cleaned_data and len(self.cleaned_data['labels']) != 0:
            labels = self.cleaned_data['labels']
        else:
            labels = None

        if 'parent' in self.cleaned_data:
            parent = self.cleaned_data['parent']
        else:
            parent = None

        if parent is None and labels is None:
            raise forms.ValidationError(_("Labels are required if no Parent is selected"))

        if parent is not None:
            labels = parent.labels.all()

        return labels

    class Meta:
        model = FAQ
        fields = ('question', 'answer', 'language', 'parent', 'labels')
