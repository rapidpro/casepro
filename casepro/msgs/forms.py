from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _

from casepro.utils import parse_csv, normalize

from .models import Label


class LabelForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=128)

    description = forms.CharField(label=_("Description"), max_length=255, widget=forms.Textarea)

    keywords = forms.CharField(label=_("Keywords"), widget=forms.Textarea, required=False,
                               help_text=_("Match messages containing any of these words"))

    def __init__(self, *args, **kwargs):
        is_create = kwargs.pop('is_create')

        super(LabelForm, self).__init__(*args, **kwargs)

        # don't let users change names of existing labels
        if not is_create:
            self.fields['name'].widget = forms.TextInput(attrs={'readonly': 'readonly'})

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if name.lower() == 'flagged':
            raise forms.ValidationError(_("Reserved label name"))
        elif name.startswith('+') or name.startswith('-'):
            raise forms.ValidationError(_("Label name cannot start with + or -"))
        return name

    def clean_keywords(self):
        keywords = parse_csv(self.cleaned_data['keywords'])
        clean_keywords = []
        for keyword in keywords:
            clean_keyword = normalize(keyword)

            if len(keyword) < Label.KEYWORD_MIN_LENGTH:
                raise forms.ValidationError(_("Keywords must be at least %d characters long")
                                            % Label.KEYWORD_MIN_LENGTH)

            if not Label.is_valid_keyword(keyword):
                raise forms.ValidationError(_("Invalid keyword: %s") % keyword)

            clean_keywords.append(clean_keyword)

        return ','.join(clean_keywords)

    class Meta:
        model = Label
        fields = ('name', 'description', 'keywords')
