from casepro.msgs.models import Label, Message, MessageAction
from casepro.contacts.models import Contact, Group, Field
from dash.test import DashTest
from dash.orgs.models import Org
from django.utils.timezone import now
import pytz
from datetime import datetime


def create_message(org, backend_id, contact, text, labels=(), **kwargs):
    if 'type' not in kwargs:
        kwargs['type'] = 'I'
    if 'created_on' not in kwargs:
        kwargs['created_on'] = now()
    msg = Message.objects.create(org=org, backend_id=backend_id, contact=contact, text=text, **kwargs)
    msg.labels.add(*labels)
    return msg


def create_contact(org, uuid, name, groups=(), fields=None, is_stub=False):
    contact = Contact.objects.create(org=org, uuid=uuid, name=name, is_stub=is_stub, fields=fields, language="eng")
    contact.groups.add(*groups)
    return contact

org = Org.objects.get(pk=1)
contact = create_contact(org, 'C-001', "Ann")
label = Label.objects.get(pk=1)

d1 = datetime(2016, 5, 24, 9, 0, tzinfo=pytz.UTC)
msg3 = create_message(org, 103, contact, "More Normal stuff", [label], created_on=d1, is_handled=True, has_labels=True)
