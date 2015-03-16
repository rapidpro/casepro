from __future__ import absolute_import, unicode_literals

from dash.orgs.views import OrgPermsMixin
from django import forms
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from smartmin.users.views import SmartCRUDL, SmartFormView, SmartListView
from upartners.labels.models import Label


class LabelCRUDL(SmartCRUDL):
    actions = ('select', 'list')
    model = Label

    class Select(OrgPermsMixin, SmartFormView):
        class LabelsForm(forms.Form):
            labels = forms.MultipleChoiceField(choices=(), label=_("Labels"),
                                               help_text=_("Message labels to use for delegating messages."))

            def __init__(self, *args, **kwargs):
                org = kwargs['org']
                del kwargs['org']
                super(LabelCRUDL.Select.LabelsForm, self).__init__(*args, **kwargs)

                choices = []
                for label in org.get_temba_client().get_labels():
                    choices.append((label.uuid, "%s (%d)" % (label.name, label.count)))

                self.fields['labels'].choices = choices
                self.fields['labels'].initial = [room.uuid for room in Label.get_all(org)]

        title = _("Message Labels")
        form_class = LabelsForm
        success_url = '@labels.label_list'
        submit_button_name = _("Update")
        success_message = _("Updated message labels")

        def get_form_kwargs(self):
            kwargs = super(LabelCRUDL.Select, self).get_form_kwargs()
            kwargs['org'] = self.request.user.get_org()
            return kwargs

        def form_valid(self, form):
            Label.update_labels(self.request.user.get_org(), form.cleaned_data['labels'])
            return HttpResponseRedirect(self.get_success_url())

    class List(OrgPermsMixin, SmartListView):
        fields = ('name', 'count')
