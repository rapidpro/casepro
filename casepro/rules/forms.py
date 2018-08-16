from django import forms

from casepro.contacts.models import Field
from casepro.utils import parse_csv

from .models import FieldTest


class FieldTestWidget(forms.widgets.MultiWidget):

    template_name = "widgets/fieldtest.html"

    def decompress(self, test):
        if test:
            return test.key, ", ".join(test.values)
        else:
            return None, ""


class FieldTestField(forms.fields.MultiValueField):
    def __init__(self, *args, **kwargs):
        org = kwargs.pop("org")
        org_fields = Field.get_all(org).order_by("label")

        fields = (
            forms.ModelChoiceField(queryset=org_fields, required=False, to_field_name="key"),
            forms.CharField(max_length=64),
        )
        widgets = (fields[0].widget, fields[1].widget)

        super(FieldTestField, self).__init__(fields, *args, **kwargs)

        self.widget = FieldTestWidget(widgets)

    def compress(self, values):
        field, values_csv = values if values else (None, "")
        if field:
            return FieldTest(field.key, parse_csv(values[1]))
        else:
            return None
