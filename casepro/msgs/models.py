from __future__ import unicode_literals

from dash.orgs.models import Org
from django.contrib.auth.models import User
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


class Outgoing(models.Model):
    """
    An outgoing message (i.e. broadcast) sent by a user
    """
    BULK_REPLY = 'B'
    CASE_REPLY = 'C'
    FORWARD = 'F'

    ACTIVITY_CHOICES = ((BULK_REPLY, _("Bulk Reply")), (CASE_REPLY, "Case Reply"), (FORWARD, _("Forward")))

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='outgoing_messages')

    activity = models.CharField(max_length=1, choices=ACTIVITY_CHOICES)

    text = models.TextField(max_length=640, null=True)

    broadcast_id = models.IntegerField()

    recipient_count = models.PositiveIntegerField()

    created_by = models.ForeignKey(User, related_name="outgoing_messages")

    created_on = models.DateTimeField(db_index=True)

    case = models.ForeignKey('cases.Case', null=True, related_name="outgoing_messages")

    @classmethod
    def create(cls, org, user, activity, text, urns, contacts, case=None):
        if not text:
            raise ValueError("Message text cannot be empty")

        broadcast = org.get_temba_client().create_broadcast(text=text, urns=urns, contacts=contacts)

        # TODO update RapidPro api to expose more accurate recipient_count
        recipient_count = len(broadcast.urns) + len(broadcast.contacts)

        return cls.objects.create(org=org,
                                  broadcast_id=broadcast.id,
                                  recipient_count=recipient_count,
                                  activity=activity, case=case,
                                  text=text,
                                  created_by=user,
                                  created_on=broadcast.created_on)

    def as_json(self):
        return {'id': self.pk,
                'text': self.text,
                'contact': self.case.contact.pk,
                'urn': None,
                'time': self.created_on,
                'labels': [],
                'flagged': False,
                'direction': 'O',
                'archived': False,
                'sender': self.created_by.as_json()}
