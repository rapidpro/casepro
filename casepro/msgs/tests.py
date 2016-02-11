# coding=utf-8
from __future__ import unicode_literals

import pytz

from casepro.cases.models import Case, CaseEvent, Contact
from casepro.dash_ext.tests import MockClientQuery
from casepro.test import BaseCasesTest
from datetime import datetime, timedelta
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from django.utils import timezone
from mock import patch, call
from temba_client.v1.types import Contact as TembaContact
from temba_client.v1.types import Message as TembaMessage, Broadcast as TembaBroadcast
from .models import Outgoing, MessageExport
from .tasks import pull_messages


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
    @patch('dash.orgs.models.TembaClient1.label_messages')
    @patch('dash.orgs.models.TembaClient1.archive_messages')
    def test_pull_messages(self, mock_archive_messages, mock_label_messages, mock_get_messages):
        d1 = datetime(2014, 1, 1, 7, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 1, 8, 0, tzinfo=timezone.utc)
        d3 = datetime(2014, 1, 1, 9, 0, tzinfo=timezone.utc)
        d4 = datetime(2014, 1, 1, 10, 0, tzinfo=timezone.utc)
        d5 = datetime(2014, 1, 1, 11, 0, tzinfo=timezone.utc)
        msg1 = TembaMessage.create(id=101, contact='C-001', text="What is aids?", created_on=d1)
        msg2 = TembaMessage.create(id=102, contact='C-002', text="Can I catch Hiv?", created_on=d2)
        msg3 = TembaMessage.create(id=103, contact='C-003', text="I think I'm pregnant", created_on=d3)
        msg4 = TembaMessage.create(id=104, contact='C-004', text="Php is amaze", created_on=d4)
        msg5 = TembaMessage.create(id=105, contact='C-005', text="Thanks for the pregnancy/HIV info", created_on=d5)
        mock_get_messages.side_effect = [
            MockClientQuery([msg1, msg2, msg3, msg4, msg5])
        ]

        # contact 5 has a case open that day
        d1 = datetime(2014, 1, 1, 5, 0, tzinfo=timezone.utc)
        with patch.object(timezone, 'now', return_value=d1):
            contact5 = Contact.get_or_create(self.unicef, 'C-005')
            case1 = Case.objects.create(org=self.unicef, contact=contact5,
                                        assignee=self.moh, message_id=99, message_on=d1)

        pull_messages(self.unicef.pk)

        task_state = self.unicef.get_task_state('message-pull')

        call_kwargs = mock_get_messages.call_args[1]
        self.assertEqual(call_kwargs['after'], task_state.started_on - timedelta(hours=1))
        self.assertEqual(call_kwargs['before'], task_state.started_on)

        mock_label_messages.assert_has_calls([
            call(messages=[msg1, msg2], label_uuid='L-001'),
            call(messages=[msg3], label_uuid='L-002')
        ], any_order=True)

        mock_archive_messages.assert_called_once_with(messages=[msg5])  # because contact has open case

        # check reply event was created for message 5
        events = case1.events.all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, CaseEvent.REPLY)
        self.assertEqual(events[0].created_on, d5)

        # check task result
        task_state = self.unicef.get_task_state('message-pull')
        self.assertEqual(task_state.get_last_results(), {'messages': 5, 'labelled': 3})
