from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _

from casepro.contacts.models import Group
from casepro.rules.forms import FieldTestField
from casepro.utils import parse_csv, normalize

from .models import Label


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
