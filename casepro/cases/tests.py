# coding=utf-8
from __future__ import absolute_import, unicode_literals

from casepro.msgs.models import Message, Outgoing
from casepro.msgs.tasks import handle_messages
from casepro.profiles import ROLE_ANALYST, ROLE_MANAGER
from casepro.test import BaseCasesTest
from casepro.utils import datetime_to_microseconds, microseconds_to_datetime
from dash.test import MockClientQuery
from datetime import datetime
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.utils import timezone
from mock import patch
from temba_client.v1.types import Label as TembaLabel, Broadcast as TembaBroadcast
from temba_client.v2.types import Contact as TembaContact, ObjectRef, Message as TembaMessage
from .context_processors import contact_ext_url, sentry_dsn
from .models import AccessLevel, Case, CaseAction, CaseEvent, Contact, Label, Partner


class CaseTest(BaseCasesTest):
    def setUp(self):
        super(CaseTest, self).setUp()

        self.bob = self.create_contact(self.unicef, 'C-001', "Bob",
                                       fields={'age': "34"}, groups=[self.males, self.reporters])

    @patch('casepro.test.TestBackend.archive_contact_messages')
    @patch('casepro.test.TestBackend.archive_messages')
    @patch('casepro.test.TestBackend.stop_runs')
    @patch('casepro.test.TestBackend.add_to_group')
    @patch('casepro.test.TestBackend.remove_from_group')
    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_lifecycle(self, mock_get_contacts, mock_remove_from_group, mock_add_to_group,
                       mock_stop_runs, mock_archive_messages, mock_archive_contact_messages):

        d0 = datetime(2014, 1, 2, 6, 0, tzinfo=timezone.utc)
        d1 = datetime(2014, 1, 2, 7, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 2, 8, 0, tzinfo=timezone.utc)
        d3 = datetime(2014, 1, 2, 9, 0, tzinfo=timezone.utc)
        d4 = datetime(2014, 1, 2, 10, 0, tzinfo=timezone.utc)
        d5 = datetime(2014, 1, 2, 11, 0, tzinfo=timezone.utc)
        d6 = datetime(2014, 1, 2, 12, 0, tzinfo=timezone.utc)
        d7 = datetime(2014, 1, 2, 13, 0, tzinfo=timezone.utc)

        msg1 = TembaMessage.create(id=123, contact=ObjectRef.create(uuid='C-001', name="Bob"), created_on=d0, text="Hello")
        msg2 = TembaMessage.create(id=234, contact=ObjectRef.create(uuid='C-001', name="Bob"), created_on=d1, text="Hello again")

        mock_get_contacts.return_value = MockClientQuery([
            TembaContact.create(uuid='C-001', name="Bob", blocked=False, fields={'age': "34"}, groups=[
                ObjectRef.create(uuid='G-001', name="Males"),
                ObjectRef.create(uuid='G-003', name="Reporters"),
            ])
        ])

        with patch.object(timezone, 'now', return_value=d1):
            # MOH opens new case
            case = Case.get_or_open(self.unicef, self.user1, [self.aids], msg2, "Summary", self.moh)

        self.assertTrue(case.is_new)
        self.assertEqual(case.org, self.unicef)
        self.assertEqual(set(case.labels.all()), {self.aids})
        self.assertEqual(case.assignee, self.moh)
        self.assertEqual(case.contact, self.bob)
        self.assertEqual(case.message_id, 234)
        self.assertEqual(case.message_on, d1)
        self.assertEqual(case.summary, "Summary")
        self.assertEqual(case.opened_on, d1)
        self.assertIsNone(case.closed_on)

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action, CaseAction.OPEN)
        self.assertEqual(actions[0].created_by, self.user1)
        self.assertEqual(actions[0].created_on, d1)
        self.assertEqual(actions[0].assignee, self.moh)

        # check that opening the case archived the contact's messages
        mock_archive_contact_messages.assert_called_once_with(self.unicef, self.bob)
        mock_archive_contact_messages.reset_mock()

        # check that opening the case removed contact from specified suspend groups
        mock_remove_from_group.assert_called_once_with(self.unicef, self.bob, self.reporters)
        mock_remove_from_group.reset_mock()

        # check that contacts groups were restored
        self.assertEqual(set(Contact.objects.get(pk=self.bob.pk).groups.all()), {self.males})
        self.assertEqual(set(Contact.objects.get(pk=self.bob.pk).suspended_groups.all()), {self.reporters})

        # check that contact's runs were expired
        mock_stop_runs.assert_called_once_with(self.unicef, self.bob)
        mock_stop_runs.reset_mock()

        # check access to this case
        self.assertEqual(case.access_level(self.user1), AccessLevel.update)  # user who opened it can view and update
        self.assertEqual(case.access_level(self.user2), AccessLevel.update)  # user from same org can do likewise
        self.assertEqual(case.access_level(self.user3), AccessLevel.read)  # user from other partner can read bc labels
        self.assertEqual(case.access_level(self.user4), AccessLevel.none)  # user from different org

        # check that calling get_or_open again returns the same case (finds open case for contact)
        with patch.object(timezone, 'now', return_value=d2):
            case2 = Case.get_or_open(self.unicef, self.user1, [self.aids], msg2, "Summary", self.moh)
            self.assertFalse(case2.is_new)
            self.assertEqual(case, case2)

        # contact sends a reply
        self.create_message(self.unicef, 432, self.bob, "OK", d2)
        handle_messages(self.unicef.pk)

        events = case.events.order_by('pk')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, CaseEvent.REPLY)
        self.assertEqual(events[0].created_on, d2)

        # which will have been archived
        mock_archive_messages.assert_called_once_with(self.unicef, list(Message.objects.filter(backend_id=432)))
        mock_archive_messages.reset_mock()

        with patch.object(timezone, 'now', return_value=d2):
            # other user in MOH adds a note
            case.add_note(self.user2, "Interesting")

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[1].action, CaseAction.ADD_NOTE)
        self.assertEqual(actions[1].created_by, self.user2)
        self.assertEqual(actions[1].created_on, d2)
        self.assertEqual(actions[1].note, "Interesting")

        # user from other partner org can't re-assign or close case
        self.assertRaises(PermissionDenied, case.reassign, self.user3)
        self.assertRaises(PermissionDenied, case.close, self.user3)

        with patch.object(timezone, 'now', return_value=d3):
            # first user closes the case
            case.close(self.user1)

        self.assertEqual(case.opened_on, d1)
        self.assertEqual(case.closed_on, d3)

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[2].action, CaseAction.CLOSE)
        self.assertEqual(actions[2].created_by, self.user1)
        self.assertEqual(actions[2].created_on, d3)

        # check that contacts groups were restored
        self.assertEqual(set(Contact.objects.get(pk=self.bob.pk).groups.all()), {self.males, self.reporters})
        self.assertEqual(set(Contact.objects.get(pk=self.bob.pk).suspended_groups.all()), set())

        mock_add_to_group.assert_called_once_with(self.unicef, self.bob, self.reporters)
        mock_add_to_group.reset_mock()

        # contact sends a message after case was closed
        self.create_message(self.unicef, 345, self.bob, "No more case", d4)
        handle_messages(self.unicef.pk)

        # message is not in an open case, so won't have been archived
        mock_archive_messages.assert_not_called()

        with patch.object(timezone, 'now', return_value=d4):
            # but second user re-opens it
            case.reopen(self.user2)

        self.assertEqual(case.opened_on, d1)  # unchanged
        self.assertIsNone(case.closed_on)

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 4)
        self.assertEqual(actions[3].action, CaseAction.REOPEN)
        self.assertEqual(actions[3].created_by, self.user2)
        self.assertEqual(actions[3].created_on, d4)

        # check that re-opening the case archived the contact's messages again
        mock_archive_contact_messages.assert_called_once_with(self.unicef, self.bob)

        with patch.object(timezone, 'now', return_value=d5):
            # and re-assigns it to different partner
            case.reassign(self.user2, self.who)

        self.assertEqual(case.assignee, self.who)

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 5)
        self.assertEqual(actions[4].action, CaseAction.REASSIGN)
        self.assertEqual(actions[4].created_by, self.user2)
        self.assertEqual(actions[4].created_on, d5)
        self.assertEqual(actions[4].assignee, self.who)

        with patch.object(timezone, 'now', return_value=d6):
            # user from that partner re-labels it
            case.update_labels(self.user3, [self.pregnancy])

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 7)
        self.assertEqual(actions[5].action, CaseAction.LABEL)
        self.assertEqual(actions[5].created_by, self.user3)
        self.assertEqual(actions[5].created_on, d6)
        self.assertEqual(actions[5].label, self.pregnancy)
        self.assertEqual(actions[6].action, CaseAction.UNLABEL)
        self.assertEqual(actions[6].created_by, self.user3)
        self.assertEqual(actions[6].created_on, d6)
        self.assertEqual(actions[6].label, self.aids)

        with patch.object(timezone, 'now', return_value=d7):
            # user from that partner org closes it again
            case.close(self.user3)

        self.assertEqual(case.opened_on, d1)
        self.assertEqual(case.closed_on, d7)

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 8)
        self.assertEqual(actions[7].action, CaseAction.CLOSE)
        self.assertEqual(actions[7].created_by, self.user3)
        self.assertEqual(actions[7].created_on, d7)

        # check that calling get_or_open again returns the same case (finds case for same message)
        case3 = Case.get_or_open(self.unicef, self.user1, [self.aids], msg2, "Summary", self.moh)
        self.assertFalse(case3.is_new)
        self.assertEqual(case, case3)

    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_get_all(self, mock_get_contacts):
        self.create_contact(self.unicef, 'C-002', "Richard")
        self.create_contact(self.unicef, 'C-003', "Kidus")
        self.create_contact(self.nyaruka, 'C-004', "Norbert")

        mock_get_contacts.side_effect = [
            MockClientQuery([TembaContact.create(uuid='C-001', name="Ann", blocked=False, fields={}, groups=[])]),
            MockClientQuery([TembaContact.create(uuid='C-002', name="Bob", blocked=False, fields={}, groups=[])]),
            MockClientQuery([TembaContact.create(uuid='C-003', name="Cat", blocked=False, fields={}, groups=[])]),
            MockClientQuery([TembaContact.create(uuid='C-004', name="Don", blocked=False, fields={}, groups=[])]),
        ]

        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=timezone.utc)
        msg1 = TembaMessage.create(id=123, contact=ObjectRef.create(uuid='C-001', name="Ann"), created_on=d1, text="Hello 1")
        case1 = Case.get_or_open(self.unicef, self.user1, [self.aids], msg1, "Summary", self.moh,
                                 update_contact=False)
        msg2 = TembaMessage.create(id=234, contact=ObjectRef.create(uuid='C-002', name="Bob"), created_on=d1, text="Hello 2")
        case2 = Case.get_or_open(self.unicef, self.user2, [self.aids, self.pregnancy], msg2, "Summary", self.who,
                                 update_contact=False)
        msg3 = TembaMessage.create(id=345, contact=ObjectRef.create(uuid='C-003', name="Cat"), created_on=d1, text="Hello 3")
        case3 = Case.get_or_open(self.unicef, self.user3, [self.pregnancy], msg3, "Summary", self.who,
                                 update_contact=False)
        msg4 = TembaMessage.create(id=456, contact=ObjectRef.create(uuid='C-004', name="Don"), created_on=d1, text="Hello 4")
        case4 = Case.get_or_open(self.nyaruka, self.user4, [self.code], msg4, "Summary", self.klab,
                                 update_contact=False)

        self.assertEqual(set(Case.get_all(self.unicef)), {case1, case2, case3})  # org admins see all
        self.assertEqual(set(Case.get_all(self.nyaruka)), {case4})

        self.assertEqual(set(Case.get_all(self.unicef, user=self.user1)), {case1, case2, case3})  # case3 by label
        self.assertEqual(set(Case.get_all(self.unicef, user=self.user2)), {case1, case2, case3})
        self.assertEqual(set(Case.get_all(self.unicef, user=self.user3)), {case1, case2, case3})  # case3 by assignment
        self.assertEqual(set(Case.get_all(self.nyaruka, user=self.user4)), {case4})

        self.assertEqual(set(Case.get_all(self.unicef, label=self.aids)), {case1, case2})
        self.assertEqual(set(Case.get_all(self.unicef, label=self.pregnancy)), {case2, case3})

        self.assertEqual(set(Case.get_all(self.unicef, user=self.user1, label=self.pregnancy)), {case2, case3})
        self.assertEqual(set(Case.get_all(self.unicef, user=self.user3, label=self.pregnancy)), {case2, case3})

        case2.closed_on = timezone.now()
        case2.save()

        self.assertEqual(set(Case.get_open(self.unicef)), {case1, case3})
        self.assertEqual(set(Case.get_open(self.unicef, user=self.user1, label=self.pregnancy)), {case3})

        self.assertEqual(set(Case.get_closed(self.unicef)), {case2})
        self.assertEqual(set(Case.get_closed(self.unicef, user=self.user1, label=self.pregnancy)), {case2})

    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_get_open_for_contact_on(self, mock_get_contacts):
        d0 = datetime(2014, 1, 5, 0, 0, tzinfo=timezone.utc)
        d1 = datetime(2014, 1, 10, 0, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 15, 0, 0, tzinfo=timezone.utc)

        mock_get_contacts.return_value = MockClientQuery([
            TembaContact.create(uuid='C-001', name="Bob", blocked=False, fields={}, groups=[])
        ])

        # case Jan 5th -> Jan 10th
        with patch.object(timezone, 'now', return_value=d0):
            msg = TembaMessage.create(id=123, contact=ObjectRef.create(uuid='C-001', name="Bob"), created_on=d0, text="Hello")
            case1 = Case.get_or_open(self.unicef, self.user1, [self.pregnancy], msg, "Summary", self.moh,
                                     update_contact=False)
        with patch.object(timezone, 'now', return_value=d1):
            case1.close(self.user1)

        # case Jan 15th -> now
        with patch.object(timezone, 'now', return_value=d2):
            msg = TembaMessage.create(id=234, contact=ObjectRef.create(uuid='C-001', name="Bob"), created_on=d0, text="Hello")
            case2 = Case.get_or_open(self.unicef, self.user1, [self.aids], msg, "Summary", self.moh,
                                     update_contact=False)

        # check no cases open on Jan 4th
        open_case = Case.get_open_for_contact_on(self.unicef, self.bob, datetime(2014, 1, 4, 0, 0, tzinfo=timezone.utc))
        self.assertIsNone(open_case)

        # check case open on Jan 7th
        open_case = Case.get_open_for_contact_on(self.unicef, self.bob, datetime(2014, 1, 7, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(open_case, case1)

        # check no cases open on Jan 13th
        open_case = Case.get_open_for_contact_on(self.unicef, self.bob, datetime(2014, 1, 13, 0, 0, tzinfo=timezone.utc))
        self.assertIsNone(open_case)

        # check case open on 20th
        open_case = Case.get_open_for_contact_on(self.unicef, self.bob, datetime(2014, 1, 16, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(open_case, case2)


class CaseCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(CaseCRUDLTest, self).setUp()

        self.bob = self.create_contact(self.unicef, 'C-001', "Bob",
                                       fields={'age': "34"}, groups=[self.males, self.reporters])

    @patch('casepro.test.TestBackend.archive_contact_messages')
    @patch('casepro.test.TestBackend.stop_runs')
    @patch('casepro.test.TestBackend.add_to_group')
    @patch('casepro.test.TestBackend.remove_from_group')
    @patch('dash.orgs.models.TembaClient2.get_messages')
    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_open(self, mock_get_contacts, mock_get_messages,
                  mock_remove_contacts, mock_add_contacts, mock_stop_runs, mock_archive_contact_messages):
        self.create_contact(self.unicef, 'C-002', "Richard")

        url = reverse('cases.case_open')

        msg1 = TembaMessage.create(id=101,
                                   contact=ObjectRef.create(uuid='C-001', name="Bob"),
                                   text="Hello",
                                   direction='in',
                                   labels=[ObjectRef.create(uuid='L-001', name="AIDS")],
                                   created_on=timezone.now())

        mock_get_messages.return_value = MockClientQuery([msg1])
        mock_get_contacts.return_value = MockClientQuery([
            TembaContact.create(uuid='C-001', name="Bob", blocked=False, fields={}, groups=[
                ObjectRef.create(uuid='G-021', name="A"),
                ObjectRef.create(uuid='G-022', name="B"),
                ObjectRef.create(uuid='G-023', name="C")
            ])
        ])

        # log in as an administrator
        self.login(self.admin)

        response = self.url_post('unicef', url, {'message': 101, 'summary': "Summary", 'assignee': self.moh.pk})
        self.assertEqual(response.status_code, 200)

        self.assertTrue(response.json['is_new'])
        self.assertEqual(response.json['case']['summary'], "Summary")

        case1 = Case.objects.get(pk=response.json['case']['id'])
        self.assertEqual(case1.message_id, 101)
        self.assertEqual(case1.summary, "Summary")
        self.assertEqual(case1.assignee, self.moh)
        self.assertEqual(set(case1.labels.all()), {self.aids})

        # try again as a non-administrator who can't create cases for other partner orgs
        msg2 = TembaMessage.create(id=102,
                                   contact=ObjectRef.create(uuid='C-002', name="Guy"),
                                   text="Hello",
                                   direction='in',
                                   labels=[ObjectRef.create(uuid='L-001', name="AIDS")],
                                   created_on=timezone.now())

        mock_get_messages.return_value = MockClientQuery([msg2])
        mock_get_contacts.return_value = MockClientQuery([
            TembaContact.create(uuid='C-002', name="Guy", blocked=False, fields={}, groups=[
                ObjectRef.create(uuid='G-021', name="A"),
                ObjectRef.create(uuid='G-022', name="B"),
                ObjectRef.create(uuid='G-023', name="C")
            ])
        ])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post('unicef', url, {'message': 101, 'summary': "Summary"})
        self.assertEqual(response.status_code, 200)

        case2 = Case.objects.get(pk=response.json['case']['id'])
        self.assertEqual(case2.message_id, 102)
        self.assertEqual(case2.summary, "Summary")
        self.assertEqual(case2.assignee, self.moh)
        self.assertEqual(set(case2.labels.all()), {self.aids})

    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_read(self, mock_get_contacts):
        msg = TembaMessage.create(id=101, contact=ObjectRef.create(uuid='C-001', name="Bob"),
                                  created_on=timezone.now(), text="Hello",
                                  direction='I', labels=[])
        mock_get_contacts.return_value = MockClientQuery([
            TembaContact.create(uuid='C-001', name="Bob", blocked=False, fields={}, groups=[])
        ])

        case = Case.get_or_open(self.unicef, self.user1, [self.aids], msg, "Summary", self.moh, update_contact=False)

        url = reverse('cases.case_read', args=[case.pk])

        # log in as non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

    @patch('casepro.test.TestBackend.archive_messages')
    @patch('dash.orgs.models.TembaClient2.get_messages')
    @patch('dash.orgs.models.TembaClient1.create_broadcast')
    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_timeline(self, mock_get_contacts, mock_create_broadcast, mock_get_messages, mock_archive_messages):
        d1 = datetime(2014, 1, 2, 13, 0, tzinfo=timezone.utc)

        msg1 = TembaMessage.create(id=102,
                                   contact=ObjectRef.create(uuid='C-001', name="Bob"),
                                   created_on=d1, text="What is AIDS?", type='inbox', direction='in',
                                   labels=[ObjectRef.create(uuid='L-001', name="AIDS")])
        mock_get_messages.return_value = MockClientQuery([msg1])
        mock_get_contacts.return_value = MockClientQuery([
            TembaContact.create(uuid='C-001', name="Bob", blocked=False, fields={}, groups=[])
        ])

        case = Case.get_or_open(self.unicef, self.user1, [self.aids], msg1, "Summary", self.moh, update_contact=False)

        timeline_url = reverse('cases.case_timeline', args=[case.pk])

        # log in as non-administrator
        self.login(self.user1)

        # request all of a timeline up to now
        response = self.url_get('unicef', '%s?after=' % timeline_url)
        t0 = microseconds_to_datetime(response.json['max_time'])

        self.assertEqual(len(response.json['results']), 2)
        self.assertEqual(response.json['results'][0]['type'], 'M')
        self.assertEqual(response.json['results'][0]['item']['text'], "What is AIDS?")
        self.assertEqual(response.json['results'][0]['item']['contact']['uuid'], 'C-001')
        self.assertEqual(response.json['results'][0]['item']['direction'], 'I')
        self.assertEqual(response.json['results'][1]['type'], 'A')
        self.assertEqual(response.json['results'][1]['item']['action'], 'O')

        mock_get_messages.assert_called_once_with(contact='C-001', after=d1, before=t0)
        mock_get_messages.reset_mock()

        mock_get_messages.return_value = MockClientQuery([])

        # page looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t0)))
        t1 = microseconds_to_datetime(response.json['max_time'])
        self.assertEqual(len(response.json['results']), 0)

        mock_get_messages.assert_called_once_with(contact='C-001', after=t0, before=t1)
        mock_get_messages.reset_mock()

        # another user adds a note
        case.add_note(self.user2, "Looks interesting")

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t1)))
        t2 = microseconds_to_datetime(response.json['max_time'])

        mock_get_messages.assert_called_once_with(contact='C-001', after=t1, before=t2)
        mock_get_messages.reset_mock()

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'A')
        self.assertEqual(response.json['results'][0]['item']['note'], "Looks interesting")

        # user sends an outgoing message
        d3 = timezone.now()
        mock_create_broadcast.return_value = TembaBroadcast.create(id=201, text="It's bad", urns=[],
                                                                   contacts=['C-001'], created_on=d3)
        Outgoing.create(self.unicef, self.user1, Outgoing.CASE_REPLY, "It's bad", [], ['C-001'], case)

        msg3 = TembaMessage.create(id=103, contact=ObjectRef.create(uuid='C-001', name="Bob"),
                                   created_on=d3, text="It's bad", type='inbox',
                                   labels=[], direction='O', broadcast=201)
        mock_get_messages.return_value = MockClientQuery([msg3])

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t2)))
        t3 = microseconds_to_datetime(response.json['max_time'])

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'M')
        self.assertEqual(response.json['results'][0]['item']['text'], "It's bad")
        self.assertEqual(response.json['results'][0]['item']['direction'], 'O')

        mock_get_messages.assert_called_once_with(contact='C-001', after=t2, before=t3)
        mock_get_messages.reset_mock()

        # contact sends a reply
        d4 = timezone.now()
        self.create_message(self.unicef, 104, self.bob, "OK thanks", d4)
        handle_messages(self.unicef.pk)

        mock_get_messages.return_value = MockClientQuery([
            TembaMessage.create(id=104, contact=ObjectRef.create(uuid='C-001', name="Bob"),
                                created_on=d4, text="OK thanks", type='inbox',
                                labels=[], direction='I')
        ])

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t3)))
        t4 = microseconds_to_datetime(response.json['max_time'])

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'M')
        self.assertEqual(response.json['results'][0]['item']['text'], "OK thanks")
        self.assertEqual(response.json['results'][0]['item']['direction'], 'I')

        mock_get_messages.assert_called_once_with(contact='C-001', after=t3, before=t4)
        mock_get_messages.reset_mock()

        mock_get_messages.return_value = MockClientQuery([])

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t4)))
        t5 = microseconds_to_datetime(response.json['max_time'])
        self.assertEqual(len(response.json['results']), 0)

        mock_get_messages.assert_called_once_with(contact='C-001', after=t4, before=t5)
        mock_get_messages.reset_mock()

        mock_get_messages.return_value = MockClientQuery([])

        # user closes case
        case.close(self.user1)

        # contact sends new message after that
        d5 = timezone.now()
        self.create_message(self.unicef, 105, self.bob, "But wait", d5)
        handle_messages(self.unicef.pk)

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t5)))
        t6 = microseconds_to_datetime(response.json['max_time'])

        mock_get_messages.assert_called_once_with(contact='C-001', after=t5, before=case.closed_on)
        mock_get_messages.reset_mock()

        # should show the close event but not the message after it
        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'A')
        self.assertEqual(response.json['results'][0]['item']['action'], 'C')

        # another look for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t6)))
        t7 = microseconds_to_datetime(response.json['max_time'])

        # nothing to see
        self.assertEqual(len(response.json['results']), 0)

        # and one last look for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t7)))

        # nothing to see
        self.assertEqual(len(response.json['results']), 0)


class HomeViewsTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient1.get_labels')
    def test_inbox(self, mock_get_labels):
        mock_get_labels.return_value = []

        url = reverse('cases.inbox')

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # should provide external contact links
        self.assertContains(response, "http://localhost:8001/contact/read/{}/")

        # log in as regular user
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # should not provide external contact links
        self.assertNotContains(response, "http://localhost:8001/contact/read/{}/")


class PartnerTest(BaseCasesTest):
    def test_create(self):
        wfp = Partner.create(self.unicef, "WFP", [self.aids, self.code], None)
        self.assertEqual(wfp.org, self.unicef)
        self.assertEqual(wfp.name, "WFP")
        self.assertEqual(unicode(wfp), "WFP")
        self.assertEqual(set(wfp.get_labels()), {self.aids, self.code})

        # create some users for this partner
        jim = self.create_user(self.unicef, wfp, ROLE_MANAGER, "Jim", "jim@wfp.org")
        kim = self.create_user(self.unicef, wfp, ROLE_ANALYST, "Kim", "kim@wfp.org")

        self.assertEqual(set(wfp.get_users()), {jim, kim})
        self.assertEqual(set(wfp.get_managers()), {jim})
        self.assertEqual(set(wfp.get_analysts()), {kim})

    def test_release(self):
        self.who.release()
        self.assertFalse(self.who.is_active)

        self.assertIsNone(User.objects.get(pk=self.user3.pk).get_partner())  # user will have been detached


class PartnerCRUDLTest(BaseCasesTest):
    def test_read(self):
        url = reverse('cases.partner_read', args=[self.moh.pk])

        # user from different partner but same org can see it
        self.login(self.user3)
        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # user from different org can't
        self.login(self.user4)

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

    def test_update(self):
        url = reverse('cases.partner_update', args=[self.moh.pk])

        # login as analyst user
        self.login(self.user2)

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # login as manager user
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        response = self.url_post('unicef', url, {'name': "MOH2"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://unicef.localhost/partner/read/%d/' % self.moh.pk)

        moh = Partner.objects.get(pk=self.moh.pk)
        self.assertEqual(moh.name, "MOH2")

    def test_delete(self):
        url = reverse('cases.partner_delete', args=[self.moh.pk])

        # try first as manager (not allowed)
        self.login(self.user1)

        response = self.url_post('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        self.assertTrue(Partner.objects.get(pk=self.moh.pk).is_active)

        # try again as administrator
        self.login(self.admin)

        response = self.url_post('unicef', url)
        self.assertEqual(response.status_code, 204)

        self.assertFalse(Partner.objects.get(pk=self.moh.pk).is_active)

    def test_list(self):
        url = reverse('cases.partner_list')

        # try again as regular user
        self.login(self.user2)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        partners = list(response.context['object_list'])
        self.assertEqual(len(partners), 2)
        self.assertEqual(partners[0].name, "MOH")
        self.assertEqual(partners[1].name, "WHO")


class ContextProcessorsTest(BaseCasesTest):
    def test_contact_ext_url(self):
        with self.settings(SITE_API_HOST='http://localhost:8001/api/v1'):
            self.assertEqual(contact_ext_url(None), {'contact_ext_url': 'http://localhost:8001/contact/read/{}/'})
        with self.settings(SITE_API_HOST='rapidpro.io'):
            self.assertEqual(contact_ext_url(None), {'contact_ext_url': 'https://rapidpro.io/contact/read/{}/'})

    def test_sentry_dsn(self):
        dsn = 'https://ir78h8v3mhz91lzgd2icxzaiwtmpsx10:58l883tax2o5cae05bj517f9xmq16a2h@app.getsentry.com/44864'
        with self.settings(SENTRY_DSN=dsn):
            self.assertEqual(sentry_dsn(None),
                             {'sentry_public_dsn': 'https://ir78h8v3mhz91lzgd2icxzaiwtmpsx10@app.getsentry.com/44864'})


class InternalViewsTest(BaseCasesTest):
    def test_status(self):
        url = reverse('internal.status')
        response = self.url_get('unicef', url)

        self.assertEqual(response.json, {'cache': "OK", 'db': "OK", 'org_tasks': 'OK'})

    def test_ping(self):
        url = reverse('internal.ping')
        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
