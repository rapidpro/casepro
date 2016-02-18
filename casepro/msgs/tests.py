# coding=utf-8
from __future__ import unicode_literals

import pytz

from casepro.cases.models import Case, CaseEvent
from casepro.contacts.models import Contact
from casepro.msgs.models import Message
from casepro.test import BaseCasesTest
from dash.test import MockClientQuery
from datetime import datetime, timedelta
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from django.utils import timezone
from mock import patch, call
from temba_client.v1.types import Contact as TembaContact
from temba_client.v1.types import Message as TembaMessage, Broadcast as TembaBroadcast
from temba_client.v2.types import Message as TembaMessage2, ObjectRef
from .models import Outgoing, MessageExport
from .tasks import pull_messages, handle_messages


class OutgoingTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient1.create_broadcast')
    def test_create(self, mock_create_broadcast):
        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=timezone.utc)
        mock_create_broadcast.return_value = TembaBroadcast.create(id=201,
                                                                   text="That's great",
                                                                   urns=[],
                                                                   contacts=['C-001', 'C-002'],
                                                                   created_on=d1)

        # create bulk reply
        outgoing = Outgoing.create(self.unicef, self.user1, Outgoing.BULK_REPLY, "That's great",
                                   urns=[], contacts=['C-001', 'C-002'])

        mock_create_broadcast.assert_called_once_with(text="That's great", urns=[], contacts=['C-001', 'C-002'])

        self.assertEqual(outgoing.org, self.unicef)
        self.assertEqual(outgoing.activity, Outgoing.BULK_REPLY)
        self.assertEqual(outgoing.broadcast_id, 201)
        self.assertEqual(outgoing.recipient_count, 2)
        self.assertEqual(outgoing.created_by, self.user1)
        self.assertEqual(outgoing.created_on, d1)
        self.assertEqual(outgoing.case, None)


class MessageExportCRUDLTest(BaseCasesTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND='memory')
    @patch('dash.orgs.models.TembaClient1.get_messages')
    @patch('dash.orgs.models.TembaClient1.get_contacts')
    def test_create_and_read(self, mock_get_contacts, mock_get_messages):
        mock_get_messages.return_value = [
            TembaMessage.create(id=101, contact='C-001', text="What is HIV?", created_on=timezone.now(),
                                labels=['AIDS']),
            TembaMessage.create(id=102, contact='C-002', text="I ♡ RapidPro", created_on=timezone.now(),
                                labels=[])
        ]
        mock_get_contacts.return_value = [
            TembaContact.create(uuid='C-001', urns=[], groups=[],
                                fields={'nickname': "Bob", 'age': 28, 'state': "WA"}),
            TembaContact.create(uuid='C-002', urns=[], groups=[],
                                fields={'nickname': "Ann", 'age': 32, 'state': "IN"})
        ]

        self.unicef.record_message_time(timezone.now(), True)

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post('unicef', '%s?view=inbox&text=&after=2015-04-01T22:00:00.000Z' % reverse('msgs.messageexport_create'))
        self.assertEqual(response.status_code, 200)

        mock_get_messages.assert_called_once_with(archived=False, labels=['AIDS', 'Pregnancy'],
                                                  contacts=None, groups=None, text='', _types=None, direction='I',
                                                  after=datetime(2015, 4, 1, 22, 0, 0, 0, pytz.UTC), before=None,
                                                  pager=None)

        mock_get_contacts.assert_called_once_with(uuids=['C-001', 'C-002'])

        export = MessageExport.objects.get()
        self.assertEqual(export.created_by, self.user1)

        read_url = reverse('msgs.messageexport_read', args=[export.pk])

        response = self.url_get('unicef', read_url)
        self.assertEqual(response.status_code, 200)

        # user from another org can't access this download
        self.login(self.norbert)

        response = self.url_get('unicef', read_url)
        self.assertEqual(response.status_code, 302)


class TasksTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient2.get_messages')
    def test_pull_messages(self, mock_get_messages):
        self.create_contact(self.unicef, 'C-001', "Ann")
        self.create_contact(self.unicef, 'C-002', "Bob")

        d1 = datetime(2014, 1, 1, 7, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 1, 8, 0, tzinfo=timezone.utc)
        d3 = datetime(2014, 1, 1, 9, 0, tzinfo=timezone.utc)
        d4 = datetime(2014, 1, 1, 10, 0, tzinfo=timezone.utc)
        d5 = datetime(2014, 1, 1, 11, 0, tzinfo=timezone.utc)

        mock_get_messages.side_effect = [
            MockClientQuery([
                TembaMessage2.create(id=101, contact=ObjectRef.create(uuid='C-001', name="Ann"),
                                     text="What is aids?", created_on=d1),
                TembaMessage2.create(id=102, contact=ObjectRef.create(uuid='C-002', name="Bob"),
                                     text="Can I catch Hiv?", created_on=d2),
                TembaMessage2.create(id=103, contact=ObjectRef.create(uuid='C-003', name="Cat"),
                                     text="I think I'm pregnant", created_on=d3),
                TembaMessage2.create(id=104, contact=ObjectRef.create(uuid='C-004', name="Don"),
                                     text="Php is amaze", created_on=d4),
                TembaMessage2.create(id=105, contact=ObjectRef.create(uuid='C-005', name="Eve"),
                                     text="Thanks for the pregnancy/HIV info", created_on=d5)
            ])
        ]

        pull_messages(self.unicef.pk)

        self.assertEqual(Contact.objects.filter(is_stub=False).count(), 2)
        self.assertEqual(Contact.objects.filter(is_stub=True).count(), 3)
        self.assertEqual(Message.objects.filter(is_handled=False).count(), 5)

        # check task result
        task_state = self.unicef.get_task_state('message-pull')
        self.assertEqual(task_state.get_last_results(), {'messages': {'created': 5, 'updated': 0, 'deleted': 0}})

        call_kwargs = mock_get_messages.call_args[1]
        self.assertEqual(call_kwargs['after'], task_state.started_on - timedelta(hours=1))
        self.assertEqual(call_kwargs['before'], task_state.started_on)

    @patch('casepro.test.TestBackend.label_messages')
    @patch('casepro.test.TestBackend.archive_messages')
    def test_handle_messages(self, mock_archive_messages, mock_label_messages):
        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        cat = self.create_contact(self.unicef, 'C-003', "Cat")
        don = self.create_contact(self.unicef, 'C-004', "Don")
        eve = self.create_contact(self.unicef, 'C-005', "Eve")
        nic = self.create_contact(self.nyaruka, 'C-0101', "Nic")

        d1 = datetime(2014, 1, 1, 7, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 1, 8, 0, tzinfo=timezone.utc)
        d3 = datetime(2014, 1, 1, 9, 0, tzinfo=timezone.utc)
        d4 = datetime(2014, 1, 1, 10, 0, tzinfo=timezone.utc)
        d5 = datetime(2014, 1, 1, 11, 0, tzinfo=timezone.utc)

        msg1 = self.create_message(self.unicef, 101, ann, "What is aids?", d1)
        msg2 = self.create_message(self.unicef, 102, bob, "Can I catch Hiv?", d2)
        msg3 = self.create_message(self.unicef, 103, cat, "I think I'm pregnant", d3)
        msg4 = self.create_message(self.unicef, 104, don, "Php is amaze", d4)
        msg5 = self.create_message(self.unicef, 105, eve, "Thanks for the pregnancy/HIV info", d5)
        msg6 = self.create_message(self.nyaruka, 106, nic, "Thanks for the pregnancy/HIV info", d5)

        # contact #5 has a case open that day
        case1 = Case.objects.create(org=self.unicef, contact=eve, assignee=self.moh, message_id=99, message_on=d1)
        case1.opened_on = d1
        case1.save()

        handle_messages(self.unicef.pk)

        self.assertEqual(set(Message.objects.filter(is_handled=True)), {msg1, msg2, msg3, msg4, msg5})
        self.assertEqual(set(Message.objects.filter(is_handled=False)), {msg6})

        mock_label_messages.assert_has_calls([
            call(self.unicef, [msg1, msg2], self.aids),
            call(self.unicef, [msg3], self.pregnancy)
        ], any_order=True)

        mock_archive_messages.assert_called_once_with(self.unicef, [msg5])  # because contact has open case

        # check reply event was created for message 5
        events = case1.events.all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, CaseEvent.REPLY)
        self.assertEqual(events[0].created_on, d5)

        # check task result
        task_state = self.unicef.get_task_state('message-handle')
        self.assertEqual(task_state.get_last_results(), {'messages': 5, 'labelled': 3})

        # check calling again...
        handle_messages(self.unicef.pk)
        task_state = self.unicef.get_task_state('message-handle')
        self.assertEqual(task_state.get_last_results(), {'messages': 0, 'labelled': 0})
