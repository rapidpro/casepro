from django import forms
from django.core.validators import validate_image_file_extension
from django.utils.translation import ugettext_lazy as _

from casepro.msgs.models import Label

from .models import Partner


class BasePartnerForm(forms.ModelForm):
    description = forms.CharField(label=_("Description"), max_length=255, required=False, widget=forms.Textarea)

    labels = forms.ModelMultipleChoiceField(
        label=_("Can Access"), queryset=Label.objects.none(), widget=forms.CheckboxSelectMultiple(), required=False
    )

    logo = forms.ImageField(label=_("Logo"), required=False, validators=[validate_image_file_extension])

    def __init__(self, *args, **kwargs):
        org = kwargs.pop("org")

        super(BasePartnerForm, self).__init__(*args, **kwargs)

        self.fields["labels"].queryset = Label.get_all(org).order_by("name")


class PartnerUpdateForm(BasePartnerForm):
    def __init__(self, *args, **kwargs):
        super(PartnerUpdateForm, self).__init__(*args, **kwargs)

        self.fields["primary_contact"].queryset = kwargs["instance"].get_users()

    class Meta:
        model = Partner
        fields = ("name", "description", "primary_contact", "logo", "is_restricted", "labels")


class PartnerCreateForm(BasePartnerForm):
    def __init__(self, *args, **kwargs):
        super(PartnerCreateForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Partner
        fields = ("name", "description", "logo", "is_restricted", "labels")
