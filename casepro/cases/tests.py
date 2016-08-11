# coding=utf-8
from __future__ import absolute_import, unicode_literals

import pytz
import six

from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.test.utils import override_settings, modify_settings
from django.utils import timezone
from mock import patch
from temba_client.utils import format_iso8601

from casepro.contacts.models import Contact
from casepro.msgs.models import Message, Outgoing
from casepro.msgs.tasks import handle_messages
from casepro.profiles.models import ROLE_ANALYST, ROLE_MANAGER, Notification
from casepro.test import BaseCasesTest
from casepro.utils import datetime_to_microseconds, microseconds_to_datetime
from casepro.pods import registry as pod_registry
from casepro.pods.tests.utils import DummyPodPlugin

from .context_processors import sentry_dsn
from .models import AccessLevel, Case, CaseAction, CaseExport, CaseFolder, Partner


class CaseTest(BaseCasesTest):
    def setUp(self):
        super(CaseTest, self).setUp()

        self.ann = self.create_contact(self.unicef, 'C-001', "Ann",
                                       fields={'age': "34"},
                                       groups=[self.females, self.reporters, self.registered])

    @patch('casepro.test.TestBackend.archive_contact_messages')
    @patch('casepro.test.TestBackend.archive_messages')
    @patch('casepro.test.TestBackend.stop_runs')
    @patch('casepro.test.TestBackend.add_to_group')
    @patch('casepro.test.TestBackend.remove_from_group')
    def test_lifecycle(self, mock_remove_from_group, mock_add_to_group, mock_stop_runs,
                       mock_archive_messages, mock_archive_contact_messages):

        d0 = datetime(2015, 1, 2, 6, 0, tzinfo=pytz.UTC)
        d1 = datetime(2015, 1, 2, 7, 0, tzinfo=pytz.UTC)
        d2 = datetime(2015, 1, 2, 8, 0, tzinfo=pytz.UTC)
        d3 = datetime(2015, 1, 2, 9, 0, tzinfo=pytz.UTC)
        d4 = datetime(2015, 1, 2, 10, 0, tzinfo=pytz.UTC)
        d5 = datetime(2015, 1, 2, 11, 0, tzinfo=pytz.UTC)
        d6 = datetime(2015, 1, 2, 12, 0, tzinfo=pytz.UTC)
        d7 = datetime(2015, 1, 2, 13, 0, tzinfo=pytz.UTC)

        self.create_message(self.unicef, 123, self.ann, "Hello", created_on=d0)
        msg2 = self.create_message(self.unicef, 234, self.ann, "Hello again", [self.aids], created_on=d1)

        with patch.object(timezone, 'now', return_value=d1):
            # MOH opens new case
            case = Case.get_or_open(self.unicef, self.user1, msg2, "Summary", self.moh)

        self.assertTrue(case.is_new)
        self.assertEqual(case.org, self.unicef)
        self.assertEqual(set(case.labels.all()), {self.aids})
        self.assertEqual(set(case.watchers.all()), {self.user1})
        self.assertEqual(case.assignee, self.moh)
        self.assertEqual(case.contact, self.ann)
        self.assertEqual(case.initial_message, msg2)
        self.assertEqual(case.summary, "Summary")
        self.assertEqual(case.opened_on, d1)
        self.assertIsNone(case.closed_on)

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action, CaseAction.OPEN)
        self.assertEqual(actions[0].created_by, self.user1)
        self.assertEqual(actions[0].created_on, d1)
        self.assertEqual(actions[0].assignee, self.moh)

        # message is now attached to the case
        msg2.refresh_from_db()
        self.assertEqual(msg2.case, case)

        # check that opening the case archived the contact's messages
        mock_archive_contact_messages.assert_called_once_with(self.unicef, self.ann)
        mock_archive_contact_messages.reset_mock()

        self.assertEqual(Message.objects.filter(contact=self.ann, is_archived=False).count(), 0)

        # check that opening the case removed contact from specified suspend groups
        mock_remove_from_group.assert_called_once_with(self.unicef, self.ann, self.reporters)
        mock_remove_from_group.reset_mock()

        # check that contacts groups were suspended
        self.assertEqual(set(Contact.objects.get(pk=self.ann.pk).groups.all()), {self.females, self.registered})
        self.assertEqual(set(Contact.objects.get(pk=self.ann.pk).suspended_groups.all()), {self.reporters})

        # check that contact's runs were expired
        mock_stop_runs.assert_called_once_with(self.unicef, self.ann)
        mock_stop_runs.reset_mock()

        # check that calling get_or_open again returns the same case (finds same case on message)
        case2 = Case.get_or_open(self.unicef, self.user1, msg2, "Summary", self.moh)
        self.assertFalse(case2.is_new)
        self.assertEqual(case, case2)

        # user #2 should be notified of this new case assignment
        self.assertEqual(Notification.objects.count(), 1)
        Notification.objects.get(user=self.user2, type=Notification.TYPE_CASE_ASSIGNMENT, case_action=actions[0])

        # contact sends a reply
        msg3 = self.create_message(self.unicef, 432, self.ann, "OK", created_on=d2)
        handle_messages(self.unicef.pk)

        # user #1 should be notified of this reply
        self.assertEqual(Notification.objects.count(), 2)
        Notification.objects.get(user=self.user1, type=Notification.TYPE_CASE_REPLY, message=msg3)

        # which will have been archived and added to the case
        mock_archive_messages.assert_called_once_with(self.unicef, [msg3])
        mock_archive_messages.reset_mock()

        msg3.refresh_from_db()
        self.assertTrue(msg3.is_archived)
        self.assertEqual(msg3.case, case)

        with patch.object(timezone, 'now', return_value=d2):
            # other user in MOH adds a note
            case.add_note(self.user2, "Interesting")

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[1].action, CaseAction.ADD_NOTE)
        self.assertEqual(actions[1].created_by, self.user2)
        self.assertEqual(actions[1].created_on, d2)
        self.assertEqual(actions[1].note, "Interesting")

        self.assertEqual(set(case.watchers.all()), {self.user1, self.user2})

        # user #1 should be notified of this new note
        self.assertEqual(Notification.objects.count(), 3)
        Notification.objects.get(user=self.user1, type=Notification.TYPE_CASE_ACTION, case_action=actions[1])

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

        # user #2 should be notified
        self.assertEqual(Notification.objects.count(), 4)
        Notification.objects.get(user=self.user2, type=Notification.TYPE_CASE_ACTION, case_action=actions[2])

        # check that contacts groups were restored
        self.assertEqual(set(Contact.objects.get(pk=self.ann.pk).groups.all()),
                         {self.females, self.reporters, self.registered})
        self.assertEqual(set(Contact.objects.get(pk=self.ann.pk).suspended_groups.all()), set())

        mock_add_to_group.assert_called_once_with(self.unicef, self.ann, self.reporters)
        mock_add_to_group.reset_mock()

        # contact sends a message after case was closed
        msg4 = self.create_message(self.unicef, 345, self.ann, "No more case", created_on=d4)
        handle_messages(self.unicef.pk)

        # message is not in an open case, so won't have been archived
        mock_archive_messages.assert_not_called()

        msg4.refresh_from_db()
        self.assertFalse(msg4.is_archived)

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

        # user #1 should be notified
        self.assertEqual(Notification.objects.count(), 5)
        Notification.objects.get(user=self.user1, type=Notification.TYPE_CASE_ACTION, case_action=actions[3])

        # check that re-opening the case archived the contact's messages again
        mock_archive_contact_messages.assert_called_once_with(self.unicef, self.ann)

        msg4.refresh_from_db()
        self.assertTrue(msg4.is_archived)

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

        # users #1 (a watcher) and #3 (a new assignee) should be notified of this re-assignment
        self.assertEqual(Notification.objects.count(), 7)
        Notification.objects.get(user=self.user1, type=Notification.TYPE_CASE_ACTION, case_action=actions[4])
        Notification.objects.get(user=self.user3, type=Notification.TYPE_CASE_ASSIGNMENT, case_action=actions[4])

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
        case3 = Case.get_or_open(self.unicef, self.user1, msg2, "Summary", self.moh)
        self.assertFalse(case3.is_new)
        self.assertEqual(case, case3)

    def test_get_all(self):
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        cat = self.create_contact(self.unicef, 'C-003', "Cat")
        nic = self.create_contact(self.nyaruka, 'C-104', "Nic")

        msg1 = self.create_message(self.unicef, 123, self.ann, "Hello 1", [self.aids])
        msg2 = self.create_message(self.unicef, 234, bob, "Hello 2", [self.aids, self.pregnancy])
        msg3 = self.create_message(self.unicef, 345, cat, "Hello 3", [self.pregnancy])
        msg4 = self.create_message(self.nyaruka, 456, nic, "Hello 4", [self.code])

        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1, [self.aids])
        case2 = self.create_case(self.unicef, bob, self.who, msg2, [self.aids, self.pregnancy])
        case3 = self.create_case(self.unicef, cat, self.who, msg3, [self.pregnancy])
        case4 = self.create_case(self.nyaruka, nic, self.klab, msg4, [self.code])

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

    def test_get_open_for_contact_on(self):
        d0 = datetime(2014, 1, 5, 0, 0, tzinfo=pytz.UTC)
        d1 = datetime(2014, 1, 10, 0, 0, tzinfo=pytz.UTC)
        d2 = datetime(2014, 1, 15, 0, 0, tzinfo=pytz.UTC)

        # case Jan 5th -> Jan 10th
        msg1 = self.create_message(self.unicef, 123, self.ann, "Hello", created_on=d0)
        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1, opened_on=d0, closed_on=d1)

        # case Jan 15th -> now
        msg2 = self.create_message(self.unicef, 234, self.ann, "Hello again", created_on=d2)
        case2 = self.create_case(self.unicef, self.ann, self.moh, msg2, opened_on=d2)

        # check no cases open on Jan 4th
        open_case = Case.get_open_for_contact_on(self.unicef, self.ann, datetime(2014, 1, 4, 0, 0, tzinfo=pytz.UTC))
        self.assertIsNone(open_case)

        # check case open on Jan 7th
        open_case = Case.get_open_for_contact_on(self.unicef, self.ann, datetime(2014, 1, 7, 0, 0, tzinfo=pytz.UTC))
        self.assertEqual(open_case, case1)

        # check no cases open on Jan 13th
        open_case = Case.get_open_for_contact_on(self.unicef, self.ann, datetime(2014, 1, 13, 0, 0, tzinfo=pytz.UTC))
        self.assertIsNone(open_case)

        # check case open on 20th
        open_case = Case.get_open_for_contact_on(self.unicef, self.ann, datetime(2014, 1, 16, 0, 0, tzinfo=pytz.UTC))
        self.assertEqual(open_case, case2)

    def test_search(self):
        d1 = datetime(2014, 1, 9, 0, 0, tzinfo=pytz.UTC)
        d2 = datetime(2014, 1, 10, 0, 0, tzinfo=pytz.UTC)
        d3 = datetime(2014, 1, 11, 0, 0, tzinfo=pytz.UTC)
        d4 = datetime(2014, 1, 12, 0, 0, tzinfo=pytz.UTC)

        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        cat = self.create_contact(self.unicef, 'C-003', "Cat")
        nic = self.create_contact(self.nyaruka, "C-005", "Nic")

        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello 1")
        msg2 = self.create_message(self.unicef, 102, self.ann, "Hello 2")
        msg3 = self.create_message(self.unicef, 103, bob, "Hello 3")
        msg4 = self.create_message(self.unicef, 104, cat, "Hello 4")

        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1, opened_on=d1, closed_on=d2)
        case2 = self.create_case(self.unicef, self.ann, self.moh, msg2, opened_on=d2)
        case3 = self.create_case(self.unicef, bob, self.who, msg3, opened_on=d3)
        case4 = self.create_case(self.unicef, cat, self.who, msg4, opened_on=d4)

        # other org
        msg5 = self.create_message(self.nyaruka, 105, nic, "Hello")
        self.create_case(self.nyaruka, nic, self.klab, msg5)

        def assert_search(user, params, results):
            self.assertEqual(list(Case.search(self.unicef, user, params)), results)

        # by org admin (sees all cases)
        assert_search(self.admin, {'folder': CaseFolder.open}, [case4, case3, case2])
        assert_search(self.admin, {'folder': CaseFolder.closed}, [case1])

        # by partner user (sees only cases assigned to them)
        assert_search(self.user1, {'folder': CaseFolder.open}, [case2])
        assert_search(self.user1, {'folder': CaseFolder.closed}, [case1])

        # by assignee
        assert_search(self.user1, {'folder': CaseFolder.open, 'assignee': self.moh.pk}, [case2])

        # by before/after
        assert_search(self.admin, {'folder': CaseFolder.open, 'before': d2}, [case2])
        assert_search(self.admin, {'folder': CaseFolder.open, 'after': d3}, [case4, case3])

    def test_access_level(self):
        msg = self.create_message(self.unicef, 234, self.ann, "Hello")
        case = self.create_case(self.unicef, self.ann, self.moh, msg, [self.aids])

        self.assertEqual(case.access_level(self.superuser), AccessLevel.update)  # superusers can update
        self.assertEqual(case.access_level(self.admin), AccessLevel.update)  # admins can update
        self.assertEqual(case.access_level(self.user1), AccessLevel.update)  # user from assigned partner can update
        self.assertEqual(case.access_level(self.user3), AccessLevel.read)  # user from other partner can read bc labels
        self.assertEqual(case.access_level(self.user4), AccessLevel.none)  # user from different org


class CaseCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(CaseCRUDLTest, self).setUp()

        self.ann = self.create_contact(self.unicef, 'C-001', "Ann",
                                       fields={'age': "34"}, groups=[self.females, self.reporters])

        msg = self.create_message(self.unicef, 101, self.ann, "Hello", [self.aids])
        self.case = self.create_case(self.unicef, self.ann, self.moh, msg, [self.aids], summary="Summary")

    @patch('casepro.test.TestBackend.archive_contact_messages')
    @patch('casepro.test.TestBackend.stop_runs')
    @patch('casepro.test.TestBackend.add_to_group')
    @patch('casepro.test.TestBackend.remove_from_group')
    def test_open(self, mock_remove_contacts, mock_add_contacts, mock_stop_runs, mock_archive_contact_messages):
        CaseAction.objects.all().delete()
        Case.objects.all().delete()
        Message.objects.all().delete()

        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello", [self.aids])

        url = reverse('cases.case_open')

        # log in as an administrator
        self.login(self.admin)

        response = self.url_post_json('unicef', url, {'message': 101, 'summary': "Summary", 'assignee': self.moh.pk})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.json['summary'], "Summary")
        self.assertEqual(response.json['is_new'], True)
        self.assertEqual(response.json['watching'], True)

        case1 = Case.objects.get(pk=response.json['id'])
        self.assertEqual(case1.initial_message, msg1)
        self.assertEqual(case1.summary, "Summary")
        self.assertEqual(case1.assignee, self.moh)
        self.assertEqual(set(case1.labels.all()), {self.aids})

        # try again as a non-administrator who can't create cases for other partner orgs
        rick = self.create_contact(self.unicef, 'C-002', "Richard")
        msg2 = self.create_message(self.unicef, 102, rick, "Hello", [self.aids])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post_json('unicef', url, {'message': 102, 'summary': "Summary"})
        self.assertEqual(response.status_code, 200)

        case2 = Case.objects.get(pk=response.json['id'])
        self.assertEqual(case2.initial_message, msg2)
        self.assertEqual(case2.summary, "Summary")
        self.assertEqual(case2.assignee, self.moh)
        self.assertEqual(set(case2.labels.all()), {self.aids})

    def test_read(self):
        url = reverse('cases.case_read', args=[self.case.pk])

        # log in as non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

    @modify_settings(INSTALLED_APPS={
        'append': 'casepro.pods.tests.utils.DummyPodPlugin'
    })
    @override_settings(PODS=[{
        'label': 'dummy_pod',
        'title': 'FooPod'
    }])
    def test_read_pods(self):
        reload(pod_registry)
        url = reverse('cases.case_read', args=[self.case.pk])
        self.login(self.user1)
        response = self.url_get('unicef', url)
        self.assertContains(response, 'FooPod')
        self.assertContains(response, DummyPodPlugin.controller)
        self.assertContains(response, DummyPodPlugin.directive)

    @modify_settings(INSTALLED_APPS={
        'append': 'casepro.pods.tests.utils.DummyPodPlugin'
    })
    def test_read_pod_resources(self):
        reload(pod_registry)
        url = reverse('cases.case_read', args=[self.case.pk])
        self.login(self.user1)
        response = self.url_get('unicef', url)

        for script in DummyPodPlugin.scripts:
            self.assertContains(response, script.rstrip('.coffee'))

        for script in DummyPodPlugin.styles:
            self.assertContains(response, script.rstrip('.less'))

    def test_note(self):
        url = reverse('cases.case_note', args=[self.case.pk])

        # log in as manager user in assigned partner
        self.login(self.user1)

        response = self.url_post_json('unicef', url, {'note': "This is a note"})
        self.assertEqual(response.status_code, 204)

        action = CaseAction.objects.get()
        self.assertEqual(action.case, self.case)
        self.assertEqual(action.action, CaseAction.ADD_NOTE)
        self.assertEqual(action.note, "This is a note")
        self.assertEqual(action.created_by, self.user1)

        # users from other partners with label access are allowed to add notes
        self.login(self.user3)

        response = self.url_post_json('unicef', url, {'note': "This is another note"})
        self.assertEqual(response.status_code, 204)

        # but not if they lose label-based access
        self.case.update_labels(self.admin, [self.pregnancy])

        response = self.url_post_json('unicef', url, {'note': "Yet another"})
        self.assertEqual(response.status_code, 403)

        # and users from other orgs certainly aren't allowed to
        self.login(self.user4)

        response = self.url_post_json('unicef', url, {'note': "Hey guys"})
        self.assertEqual(response.status_code, 302)

    def test_reassign(self):
        url = reverse('cases.case_reassign', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        response = self.url_post_json('unicef', url, {'assignee': self.who.pk, 'user_assignee': self.user3.pk})
        self.assertEqual(response.status_code, 204)

        action = CaseAction.objects.get()
        self.assertEqual(action.case, self.case)
        self.assertEqual(action.action, CaseAction.REASSIGN)
        self.assertEqual(action.created_by, self.user1)

        self.case.refresh_from_db()
        self.assertEqual(self.case.assignee, self.who)
        self.assertEqual(self.case.user_assignee, self.user3)

        # only user from assigned partner can re-assign
        response = self.url_post_json('unicef', url, {'assignee': self.moh.pk})
        self.assertEqual(response.status_code, 403)

        # can only be assigned to user from assigned partner
        response = self.url_post_json('unicef', url, {'assignee': self.who.pk, 'user_assignee': self.user2.pk})
        self.assertEqual(response.status_code, 404)

    def test_reassign_no_user(self):
        """The user field should be optional, and reassignment should still work without it."""
        url = reverse('cases.case_reassign', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        response = self.url_post_json('unicef', url, {'assignee': self.who.pk, 'user_assignee': None})
        self.assertEqual(response.status_code, 204)

    def test_close(self):
        url = reverse('cases.case_close', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        response = self.url_post_json('unicef', url, {'note': "It's over"})
        self.assertEqual(response.status_code, 204)

        action = CaseAction.objects.get()
        self.assertEqual(action.case, self.case)
        self.assertEqual(action.action, CaseAction.CLOSE)
        self.assertEqual(action.created_by, self.user1)

        self.case.refresh_from_db()
        self.assertIsNotNone(self.case.closed_on)

        # only user from assigned partner can close
        self.login(self.user3)

        self.case.reopen(self.admin, "Because")

        response = self.url_post_json('unicef', url, {'note': "It's over"})
        self.assertEqual(response.status_code, 403)

    def test_reopen(self):
        self.case.close(self.admin, "Done")

        url = reverse('cases.case_reopen', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        response = self.url_post_json('unicef', url, {'note': "Unfinished business"})
        self.assertEqual(response.status_code, 204)

        action = CaseAction.objects.get(created_by=self.user1)
        self.assertEqual(action.case, self.case)
        self.assertEqual(action.action, CaseAction.REOPEN)

        self.case.refresh_from_db()
        self.assertIsNone(self.case.closed_on)

        # only user from assigned partner can reopen
        self.login(self.user3)

        self.case.close(self.admin, "Done")

        response = self.url_post_json('unicef', url, {'note': "Unfinished business"})
        self.assertEqual(response.status_code, 403)

    def test_label(self):
        url = reverse('cases.case_label', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        # add additional label to case which this user can't access
        self.case.labels.add(self.tea)

        response = self.url_post_json('unicef', url, {'labels': [self.pregnancy.pk]})
        self.assertEqual(response.status_code, 204)

        actions = CaseAction.objects.filter(case=self.case).order_by('pk')
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].action, CaseAction.LABEL)
        self.assertEqual(actions[0].label, self.pregnancy)
        self.assertEqual(actions[1].action, CaseAction.UNLABEL)
        self.assertEqual(actions[1].label, self.aids)

        # check that tea label wasn't removed as this user doesn't have access to that label
        self.case.refresh_from_db()
        self.assertEqual(set(self.case.labels.all()), {self.pregnancy, self.tea})

        # only user from assigned partner can label
        self.login(self.user3)

        response = self.url_post_json('unicef', url, {'labels': [self.aids.pk]})
        self.assertEqual(response.status_code, 403)

    def test_update_summary(self):
        url = reverse('cases.case_update_summary', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        response = self.url_post_json('unicef', url, {'summary': "New summary"})
        self.assertEqual(response.status_code, 204)

        action = CaseAction.objects.get(case=self.case)
        self.assertEqual(action.action, CaseAction.UPDATE_SUMMARY)

        self.case.refresh_from_db()
        self.assertEqual(self.case.summary, "New summary")

        # only user from assigned partner can change the summary
        self.login(self.user3)

        response = self.url_post_json('unicef', url, {'summary': "Something else"})
        self.assertEqual(response.status_code, 403)

    def test_reply(self):
        url = reverse('cases.case_reply', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        response = self.url_post_json('unicef', url, {'text': "We can help"})
        self.assertEqual(response.status_code, 200)

        outgoing = Outgoing.objects.get()
        self.assertEqual(outgoing.activity, Outgoing.CASE_REPLY)
        self.assertEqual(outgoing.text, "We can help")
        self.assertEqual(outgoing.created_by, self.user1)

        # only user from assigned partner can reply
        self.login(self.user3)

        response = self.url_post_json('unicef', url, {'text': "Hi"})
        self.assertEqual(response.status_code, 403)

    def test_fetch(self):
        url = reverse('cases.case_fetch', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            'id': self.case.pk,
            'contact': {'id': self.ann.pk, 'name': "Ann"},
            'assignee': {'id': self.moh.pk, 'name': "MOH"},
            'labels': [{'id': self.aids.pk, 'name': "AIDS"}],
            'summary': "Summary",
            'opened_on': format_iso8601(self.case.opened_on),
            'is_closed': False,
            'watching': False
        })

        # users with label access can also fetch
        self.login(self.user3)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

    @patch('casepro.test.TestBackend.fetch_contact_messages')
    def test_timeline(self, mock_fetch_contact_messages):
        CaseAction.objects.all().delete()
        Case.objects.all().delete()
        Message.objects.all().delete()

        d0 = datetime(2014, 1, 2, 12, 0, tzinfo=pytz.UTC)
        d1 = datetime(2014, 1, 2, 13, 0, tzinfo=pytz.UTC)
        d2 = datetime(2014, 1, 2, 14, 0, tzinfo=pytz.UTC)

        # local message before case time window
        self.create_message(self.unicef, 100, self.ann, "Unrelated", [], created_on=d0)

        # create and open case
        msg1 = self.create_message(self.unicef, 101, self.ann, "What is AIDS?", [self.aids], created_on=d1)
        case = self.create_case(self.unicef, self.ann, self.moh, msg1)
        CaseAction.create(case, self.user1, CaseAction.OPEN, assignee=self.moh)
        CaseAction.create(case, None, CaseAction.ADD_NOTE, note="test note")

        # backend has a message in the case time window that we don't have locally
        remote_message1 = Outgoing(backend_broadcast_id=102, contact=self.ann, text="Non casepro message...",
                                   created_on=d2)
        mock_fetch_contact_messages.return_value = [remote_message1]

        timeline_url = reverse('cases.case_timeline', args=[case.pk])

        # log in as non-administrator
        self.login(self.user1)

        # request all of a timeline up to now
        response = self.url_get('unicef', '%s?after=' % timeline_url)
        t0 = microseconds_to_datetime(response.json['max_time'])

        self.assertEqual(len(response.json['results']), 4)
        self.assertEqual(response.json['results'][0]['type'], 'I')
        self.assertEqual(response.json['results'][0]['item']['text'], "What is AIDS?")
        self.assertEqual(response.json['results'][0]['item']['contact'], {'id': self.ann.pk, 'name': "Ann"})
        self.assertEqual(response.json['results'][1]['type'], 'O')
        self.assertEqual(response.json['results'][1]['item']['text'], "Non casepro message...")
        self.assertEqual(response.json['results'][1]['item']['contact'], {'id': self.ann.pk, 'name': "Ann"})
        self.assertEqual(response.json['results'][2]['type'], 'A')
        self.assertEqual(response.json['results'][2]['item']['action'], 'O')
        self.assertEqual(response.json['results'][3]['type'], 'A')
        self.assertEqual(response.json['results'][3]['item']['note'], "test note")

        # as this was the initial request, messages will have been fetched from the backend
        mock_fetch_contact_messages.assert_called_once_with(self.unicef, self.ann, d1, t0)
        mock_fetch_contact_messages.reset_mock()
        mock_fetch_contact_messages.return_value = []

        # page looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t0)))
        t1 = microseconds_to_datetime(response.json['max_time'])
        self.assertEqual(len(response.json['results']), 0)

        # messages won't have been fetched from the backend this time
        self.assertNotCalled(mock_fetch_contact_messages)

        # another user adds a note
        case.add_note(self.user2, "Looks interesting")

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t1)))
        t2 = microseconds_to_datetime(response.json['max_time'])

        self.assertNotCalled(mock_fetch_contact_messages)

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'A')
        self.assertEqual(response.json['results'][0]['item']['note'], "Looks interesting")

        # user sends an outgoing message
        d3 = timezone.now()
        outgoing = Outgoing.create_case_reply(self.unicef, self.user1, "It's bad", case)
        outgoing.backend_broadcast_id = 202
        outgoing.save()

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t2)))
        t3 = microseconds_to_datetime(response.json['max_time'])

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'O')
        self.assertEqual(response.json['results'][0]['item']['text'], "It's bad")

        # contact sends a reply
        d4 = timezone.now()
        self.create_message(self.unicef, 104, self.ann, "OK thanks", created_on=d4)
        handle_messages(self.unicef.pk)

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t3)))
        t4 = microseconds_to_datetime(response.json['max_time'])

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'I')
        self.assertEqual(response.json['results'][0]['item']['text'], "OK thanks")

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t4)))
        t5 = microseconds_to_datetime(response.json['max_time'])
        self.assertEqual(len(response.json['results']), 0)

        # user closes case
        case.close(self.user1)

        # contact sends new message after that
        d5 = timezone.now()
        self.create_message(self.unicef, 105, self.ann, "But wait", created_on=d5)
        handle_messages(self.unicef.pk)

        # page again looks for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t5)))
        t6 = microseconds_to_datetime(response.json['max_time'])

        # should show the close action but not the message after it
        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'A')
        self.assertEqual(response.json['results'][0]['item']['action'], 'C')

        # another look for new timeline activity
        response = self.url_get('unicef', '%s?after=%s' % (timeline_url, datetime_to_microseconds(t6)))

        # nothing to see
        self.assertEqual(len(response.json['results']), 0)

        # user now refreshes page...

        # backend has the message sent during the case as well as the unrelated message
        mock_fetch_contact_messages.return_value = [
            Outgoing(backend_broadcast_id=202, contact=self.ann, text="It's bad", created_on=d3),
            remote_message1
        ]

        # which requests all of the timeline up to now
        response = self.url_get('unicef', '%s?after=' % timeline_url)
        items = response.json['results']

        self.assertEqual(len(items), 8)
        self.assertEqual(items[0]['type'], 'I')
        self.assertEqual(items[0]['item']['text'], "What is AIDS?")
        self.assertEqual(items[0]['item']['contact'], {'id': self.ann.pk, 'name': "Ann"})
        self.assertEqual(items[1]['type'], 'O')
        self.assertEqual(items[1]['item']['text'], "Non casepro message...")
        self.assertEqual(items[1]['item']['contact'], {'id': self.ann.pk, 'name': "Ann"})
        self.assertEqual(items[1]['item']['sender'], None)
        self.assertEqual(items[2]['type'], 'A')
        self.assertEqual(items[2]['item']['action'], 'O')
        self.assertEqual(items[3]['type'], 'A')
        self.assertEqual(items[3]['item']['action'], 'N')
        self.assertEqual(items[4]['type'], 'A')
        self.assertEqual(items[4]['item']['action'], 'N')
        self.assertEqual(items[5]['type'], 'O')
        self.assertEqual(items[5]['item']['sender'], {'id': self.user1.pk, 'name': "Evan"})
        self.assertEqual(items[6]['type'], 'I')
        self.assertEqual(items[6]['item']['text'], "OK thanks")
        self.assertEqual(items[7]['type'], 'A')
        self.assertEqual(items[7]['item']['action'], 'C')

        # as this was the initial request, messages will have been fetched from the backend
        mock_fetch_contact_messages.assert_called_once_with(self.unicef, self.ann, d1, case.closed_on)
        mock_fetch_contact_messages.reset_mock()

    def test_search(self):
        url = reverse('cases.case_search')

        # create another case
        msg2 = self.create_message(self.unicef, 102, self.ann, "I ♡ RapidPro")
        case2 = self.create_case(self.unicef, self.ann, self.who, msg2)

        # try unauthenticated
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # test as org administrator
        self.login(self.admin)

        response = self.url_get('unicef', url, {'folder': 'open'})
        self.assertEqual(response.json['results'], [
            {
                'id': case2.pk,
                'assignee': {'id': self.who.pk, 'name': "WHO"},
                'contact': {'id': self.ann.pk, 'name': "Ann"},
                'labels': [],
                'summary': "",
                'opened_on': format_iso8601(case2.opened_on),
                'is_closed': False
            },
            {
                'id': self.case.pk,
                'assignee': {'id': self.moh.pk, 'name': "MOH"},
                'contact': {'id': self.ann.pk, 'name': "Ann"},
                'labels': [{'id': self.aids.pk, 'name': "AIDS"}],
                'summary': "Summary",
                'opened_on': format_iso8601(self.case.opened_on),
                'is_closed': False
            }
        ])

        # test as partner user
        self.login(self.user1)

        response = self.url_get('unicef', url, {'folder': 'open'})
        self.assertEqual(response.json['results'], [
            {
                'id': self.case.pk,
                'assignee': {'id': self.moh.pk, 'name': "MOH"},
                'contact': {'id': self.ann.pk, 'name': "Ann"},
                'labels': [{'id': self.aids.pk, 'name': "AIDS"}],
                'summary': "Summary",
                'opened_on': format_iso8601(self.case.opened_on),
                'is_closed': False
            }
        ])

    def test_watch_and_unwatch(self):
        watch_url = reverse('cases.case_watch', args=[self.case.pk])
        unwatch_url = reverse('cases.case_unwatch', args=[self.case.pk])

        # log in as manager user in currently assigned partner
        self.login(self.user1)

        response = self.url_post('unicef', watch_url)
        self.assertEqual(response.status_code, 204)

        self.assertIn(self.user1, self.case.watchers.all())

        response = self.url_post('unicef', unwatch_url)
        self.assertEqual(response.status_code, 204)

        self.assertNotIn(self.user1, self.case.watchers.all())

        # only user with case access can watch
        self.who.labels.remove(self.aids)
        self.login(self.user3)

        response = self.url_post('unicef', watch_url)
        self.assertEqual(response.status_code, 403)

        self.assertNotIn(self.user3, self.case.watchers.all())


class CaseExportCRUDLTest(BaseCasesTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND='memory')
    def test_create_and_read(self):
        ann = self.create_contact(self.unicef, "C-001", "Ann", fields={'nickname': "Annie", 'age': "28", 'state': "WA"})
        bob = self.create_contact(self.unicef, "C-002", "Bob", fields={'age': "32", 'state': "IN"})
        cat = self.create_contact(self.unicef, "C-003", "Cat", fields={'age': "64", 'state': "CA"})
        don = self.create_contact(self.unicef, "C-004", "Don", fields={'age': "22", 'state': "NV"})

        msg1 = self.create_message(self.unicef, 101, ann, "What is HIV?")
        msg2 = self.create_message(self.unicef, 102, bob, "I ♡ RapidPro")
        msg3 = self.create_message(self.unicef, 103, cat, "Hello")
        msg4 = self.create_message(self.unicef, 104, don, "Yo")

        case1 = self.create_case(self.unicef, ann, self.moh, msg1, [self.aids], summary="What is HIV?")
        case2 = self.create_case(self.unicef, bob, self.who, msg2, [self.pregnancy], summary="I ♡ RapidPro")
        self.create_case(self.unicef, cat, self.who, msg3, [], summary="Hello")
        case4 = self.create_case(self.unicef, don, self.moh, msg4, [])
        case4.close(self.user1)

        # add some messages to first case
        self.create_outgoing(self.unicef, self.user1, 201, Outgoing.CASE_REPLY, "Good question", ann, case=case1)
        self.create_message(self.unicef, 105, ann, "I know", case=case1)
        self.create_outgoing(self.unicef, self.user1, 202, Outgoing.CASE_REPLY, "It's bad", ann, case=case1)
        self.create_message(self.unicef, 106, ann, "Ok", case=case1)
        self.create_message(self.unicef, 107, ann, "U-Report rocks!", case=case1)

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post('unicef', '%s?folder=open' % reverse('cases.caseexport_create'))
        self.assertEqual(response.status_code, 200)

        export = CaseExport.objects.get()
        self.assertEqual(export.created_by, self.user1)

        workbook = self.openWorkbook(export.filename)
        sheet = workbook.sheets()[0]

        self.assertEqual(sheet.nrows, 3)
        self.assertExcelRow(sheet, 0, [
            "Message On", "Opened On", "Closed On", "Assigned Partner", "Labels", "Summary",
            "Messages Sent", "Messages Received", "Contact", "Nickname", "Age"
        ])
        self.assertExcelRow(sheet, 1, [
            msg2.created_on, case2.opened_on, "", "WHO", "Pregnancy", "I ♡ RapidPro", 0, 0, "C-002", "", "32"
        ], pytz.UTC)
        self.assertExcelRow(sheet, 2, [
            msg1.created_on, case1.opened_on, "", "MOH", "AIDS", "What is HIV?", 2, 3, "C-001", "Annie", "28"
        ], pytz.UTC)

        read_url = reverse('cases.caseexport_read', args=[export.pk])

        response = self.url_get('unicef', read_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['download_url'], "/caseexport/download/%d/?download=1" % export.pk)

        # user from another org can't access this download
        self.login(self.norbert)

        response = self.url_get('unicef', read_url)
        self.assertEqual(response.status_code, 302)


class InboxViewsTest(BaseCasesTest):
    def test_inbox(self):
        url = reverse('cases.inbox')

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertContains(response, "/org/home/")  # org-level users get link to org dashboard

        # log in as regular user
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertNotContains(response, "/org/home/")
        self.assertContains(response, "/partner/read/%d/" % self.moh.pk)  # partner users get link to partner dashboard


class PartnerTest(BaseCasesTest):
    def test_create(self):
        wfp = Partner.create(self.unicef, "WFP", True, [self.aids, self.pregnancy])
        self.assertEqual(wfp.org, self.unicef)
        self.assertEqual(wfp.name, "WFP")
        self.assertEqual(six.text_type(wfp), "WFP")
        self.assertEqual(set(wfp.get_labels()), {self.aids, self.pregnancy})

        # create some users for this partner
        jim = self.create_user(self.unicef, wfp, ROLE_MANAGER, "Jim", "jim@wfp.org")
        kim = self.create_user(self.unicef, wfp, ROLE_ANALYST, "Kim", "kim@wfp.org")

        self.assertEqual(set(wfp.get_users()), {jim, kim})
        self.assertEqual(set(wfp.get_managers()), {jim})
        self.assertEqual(set(wfp.get_analysts()), {kim})

        # create a partner which is not restricted by labels
        internal = Partner.create(self.unicef, "Internal", False, [])
        self.assertEqual(set(internal.get_labels()), {self.aids, self.pregnancy, self.tea})

        # can't create an unrestricted partner with labels
        self.assertRaises(ValueError, Partner.create, self.unicef, "Testers", False, [self.aids])

    def test_release(self):
        self.who.release()
        self.assertFalse(self.who.is_active)

        self.assertIsNone(User.objects.get(pk=self.user3.pk).get_partner(self.unicef))  # user will have been detached


class PartnerCRUDLTest(BaseCasesTest):
    def test_create(self):
        url = reverse('cases.partner_create')

        # can't access as partner user
        self.login(self.user1)
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        self.login(self.admin)
        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].fields.keys(), ['name', 'logo', 'is_restricted', 'labels', 'loc'])

        # create label restricted partner
        response = self.url_post('unicef', url, {'name': "Helpers", 'logo': None,
                                                 'is_restricted': True, 'labels': [self.tea.pk]})
        self.assertEqual(response.status_code, 302)

        helpers = Partner.objects.get(name="Helpers")
        self.assertTrue(helpers.is_restricted)
        self.assertEqual(set(helpers.get_labels()), {self.tea})

        # create unrestricted partner
        response = self.url_post('unicef', url, {'name': "Internal", 'logo': None,
                                                 'is_restricted': False, 'labels': [self.tea.pk]})
        self.assertEqual(response.status_code, 302)

        internal = Partner.objects.get(name="Internal")
        self.assertFalse(internal.is_restricted)
        self.assertEqual(set(internal.labels.all()), set())  # submitted labels are ignored
        self.assertEqual(set(internal.get_labels()), {self.aids, self.pregnancy, self.tea})

    def test_read(self):
        url = reverse('cases.partner_read', args=[self.moh.pk])

        # manager user from same partner gets full view of their own partner org
        self.login(self.user1)
        response = self.url_get('unicef', url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['can_manage'], True)
        self.assertEqual(response.context['can_view_replies'], True)

        # data-analyst user from same partner gets can't edit users
        self.login(self.user2)
        response = self.url_get('unicef', url)
        self.assertEqual(response.context['can_manage'], False)
        self.assertEqual(response.context['can_view_replies'], True)

        # user from different partner but same org has limited view
        self.login(self.user3)
        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['can_manage'], False)
        self.assertEqual(response.context['can_view_replies'], False)

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

        # try as regular user
        self.login(self.user2)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        partners = list(response.context['object_list'])
        self.assertEqual(len(partners), 2)
        self.assertEqual(partners[0].name, "MOH")
        self.assertEqual(partners[1].name, "WHO")

        response = self.url_get('unicef', url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json, {'results': [
            {'id': self.moh.pk, 'name': "MOH",  'restricted': True},
            {'id': self.who.pk, 'name': "WHO",  'restricted': True}
        ]})

        response = self.url_get('unicef', url + '?with_activity=1', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json, {'results': [
            {
                'id': self.moh.pk, 'name': "MOH", 'restricted': True,
                'replies': {'last_month': 0, 'this_month': 0, 'total': 0}
            },
            {
                'id': self.who.pk, 'name': "WHO", 'restricted': True,
                'replies': {'last_month': 0, 'this_month': 0, 'total': 0}
            }
        ]})


class ContextProcessorsTest(BaseCasesTest):
    def test_sentry_dsn(self):
        dsn = 'https://ir78h8v3mhz91lzgd2icxzaiwtmpsx10:58l883tax2o5cae05bj517f9xmq16a2h@app.getsentry.com/44864'
        with self.settings(SENTRY_DSN=dsn):
            self.assertEqual(sentry_dsn(None),
                             {'sentry_public_dsn': 'https://ir78h8v3mhz91lzgd2icxzaiwtmpsx10@app.getsentry.com/44864'})


class InternalViewsTest(BaseCasesTest):
    def test_status(self):
        url = reverse('internal.status')
        response = self.url_get('unicef', url)

        self.assertEqual(response.json, {'cache': "OK", 'org_tasks': 'OK', 'unhandled': 0})

        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        dt1 = timezone.now() - timedelta(hours=2)
        dt2 = timezone.now() - timedelta(minutes=5)

        self.create_message(self.unicef, 101, ann, "Hmm 1", created_on=dt1)
        self.create_message(self.unicef, 102, ann, "Hmm 2", created_on=dt2)

        response = self.url_get('unicef', url)

        # check only message older than 1 hour counts
        self.assertEqual(response.json, {'cache': "OK", 'org_tasks': 'OK', 'unhandled': 1})

        with patch('django.core.cache.cache.get') as mock_cache_get:
            mock_cache_get.side_effect = ValueError("BOOM")

            response = self.url_get('unicef', url)
            self.assertEqual(response.json, {'cache': "ERROR", 'org_tasks': 'OK', 'unhandled': 1})

    def test_ping(self):
        url = reverse('internal.ping')

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        with patch('dash.orgs.models.Org.objects.first') as mock_org_first:
            mock_org_first.side_effect = ValueError("BOOM")

            response = self.url_get('unicef', url)
            self.assertEqual(response.status_code, 500)
