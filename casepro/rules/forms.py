from __future__ import unicode_literals

from django import forms
from django.utils.safestring import mark_safe

from casepro.contacts.models import Field


class FieldTestWidget(forms.widgets.MultiWidget):

    def __init__(self, *args, **kwargs):
        field_choices = kwargs.pop('field_choices')
        widgets = (
            forms.Select(choices=field_choices),
            forms.TextInput(attrs={'maxlength': 64})
        )

        super(FieldTestWidget, self).__init__(widgets, *args, **kwargs)

    def decompress(self, value):
        if value:
            return value.split(':', 1)
        else:
            return None, ''

    def format_output(self, rendered_widgets):
        return mark_safe(
            '<div class="field-test-widget">' +
            rendered_widgets[0] +
            '<span class="control-label"> is equal to </span>' +
            rendered_widgets[1] +
            '</div>'
        )


class FieldTestField(forms.fields.MultiValueField):

    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org')
        org_fields = Field.get_all(org).order_by('label')

        fields = (
            forms.ModelChoiceField(queryset=org_fields, required=False),
            forms.CharField(max_length=64)
        )

        super(FieldTestField, self).__init__(fields, *args, **kwargs)

        org_field_choices = [(f.pk, f.label) for f in org_fields]

        self.widget = FieldTestWidget(field_choices=org_field_choices)

    def compress(self, values):
        return '%s:%s' % (values[0], values[1])
