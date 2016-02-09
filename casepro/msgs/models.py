from __future__ import unicode_literals

from dash.orgs.models import Org
from django.db import models
from django.utils.translation import ugettext_lazy as _


class Message(models.Model):
    """
    A incoming message from the backend
    """
    TYPE_INBOX = 'I'
    TYPE_FLOW = 'F'

    TYPE_CHOICES = ((TYPE_INBOX, _("Inbox")), (TYPE_FLOW, _("Flow")))

    org = models.ForeignKey(Org, related_name='messages', verbose_name=_("Org"))

    contact = models.ForeignKey('contacts.Contact')

    type = models.CharField(max_length=1)

    text = models.TextField(max_length=640, verbose_name=_("Text"))

    is_archived = models.BooleanField(default=False)

    created_on = models.DateTimeField()
