from __future__ import absolute_import, unicode_literals

from datetime import date, datetime
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.utils import timezone
from mock import patch, call
from temba.types import Message as TembaMessage, Broadcast as TembaBroadcast
from temba.utils import format_iso8601
from casepro.orgs_ext import TaskType
from casepro.profiles import ROLE_ANALYST, ROLE_MANAGER
from casepro.test import BaseCasesTest
from . import safe_max, truncate
from .models import Case, CaseAction, CaseEvent, Label, Message, MessageAction, Partner, Outgoing
from .tasks import process_new_org_unsolicited


class CaseTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient.get_messages')
    @patch('dash.orgs.models.TembaClient.archive_messages')
    def test_lifecyle(self, mock_archive_messages, mock_get_messages):
        d0 = datetime(2014, 1, 2, 6, 0, tzinfo=timezone.utc)
        d1 = datetime(2014, 1, 2, 7, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 2, 8, 0, tzinfo=timezone.utc)
        d3 = datetime(2014, 1, 2, 9, 0, tzinfo=timezone.utc)
        d4 = datetime(2014, 1, 2, 10, 0, tzinfo=timezone.utc)
        d5 = datetime(2014, 1, 2, 11, 0, tzinfo=timezone.utc)
        d6 = datetime(2014, 1, 2, 12, 0, tzinfo=timezone.utc)
        d7 = datetime(2014, 1, 2, 13, 0, tzinfo=timezone.utc)

        msg1 = TembaMessage.create(id=123, contact='C-001', created_on=d0, text="Hello")
        msg2 = TembaMessage.create(id=234, contact='C-001', created_on=d1, text="Hello again")
        mock_get_messages.return_value = [msg1, msg2]
        mock_archive_messages.return_value = None

        with patch.object(timezone, 'now', return_value=d1):
            # MOH opens new case
            case = Case.open(self.unicef, self.user1, [self.aids], self.moh, msg2)

        self.assertEqual(case.org, self.unicef)
        self.assertEqual(set(case.labels.all()), {self.aids})
        self.assertEqual(case.assignee, self.moh)
        self.assertEqual(case.contact_uuid, 'C-001')
        self.assertEqual(case.message_id, 234)
        self.assertEqual(case.message_on, d1)
        self.assertEqual(case.summary, "Hello again")
        self.assertEqual(case.opened_on, d1)
        self.assertIsNone(case.closed_on)

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action, CaseAction.OPEN)
        self.assertEqual(actions[0].created_by, self.user1)
        self.assertEqual(actions[0].created_on, d1)
        self.assertEqual(actions[0].assignee, self.moh)

        # check that opening the case fetched the messages and archived them
        mock_archive_messages.assert_called_once_with(messages=[123, 234])

        self.assertTrue(case.accessible_by(self.user1, update=False))  # user who opened it can view and update
        self.assertTrue(case.accessible_by(self.user1, update=True))
        self.assertTrue(case.accessible_by(self.user2, update=False))  # user from same org can also view and update
        self.assertTrue(case.accessible_by(self.user2, update=True))
        self.assertTrue(case.accessible_by(self.user3, update=False))  # user from different partner with label access
        self.assertFalse(case.accessible_by(self.user3, update=True))
        self.assertFalse(case.accessible_by(self.user4, update=False))  # user from different org
        self.assertFalse(case.accessible_by(self.user4, update=False))

        # TODO test user sends a reply

        # contact sends a reply
        case.reply_event(TembaMessage.create(created_on=d0))

        events = case.events.order_by('pk')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, CaseEvent.REPLY)
        self.assertEqual(events[0].created_on, d0)

        with patch.object(timezone, 'now', return_value=d2):
            # other user in MOH adds a note
            case.note(self.user2, "Interesting")

        actions = case.actions.order_by('pk')
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[1].action, CaseAction.NOTE)
        self.assertEqual(actions[1].created_by, self.user2)
        self.assertEqual(actions[1].created_on, d2)
        self.assertEqual(actions[1].note, "Interesting")

        # user from other partner org can't close case
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

    def test_get_all(self):
        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=timezone.utc)
        msg1 = TembaMessage.create(id=123, contact='C-001', created_on=d1, text="Hello 1")
        case1 = Case.open(self.unicef, self.user1, [self.aids], self.moh, msg1, archive_messages=False)
        msg2 = TembaMessage.create(id=234, contact='C-002', created_on=d1, text="Hello 2")
        case2 = Case.open(self.unicef, self.user2, [self.aids, self.pregnancy], self.who, msg2, archive_messages=False)
        msg3 = TembaMessage.create(id=345, contact='C-003', created_on=d1, text="Hello 3")
        case3 = Case.open(self.unicef, self.user3, [self.pregnancy], self.who, msg3, archive_messages=False)
        msg4 = TembaMessage.create(id=456, contact='C-004', created_on=d1, text="Hello 4")
        case4 = Case.open(self.nyaruka, self.user4, [self.code], self.klab, msg4, archive_messages=False)

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
        d0 = datetime(2014, 1, 5, 0, 0, tzinfo=timezone.utc)
        d1 = datetime(2014, 1, 10, 0, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 15, 0, 0, tzinfo=timezone.utc)

        # case Jan 5th -> now
        with patch.object(timezone, 'now', return_value=d0):
            msg = TembaMessage.create(id=123, contact='C-001', created_on=d0, text="Hello")
            case1 = Case.open(self.unicef, self.user1, [self.aids], self.moh, msg, archive_messages=False)

        # case Jan 5th -> Jan 10th
        with patch.object(timezone, 'now', return_value=d0):
            msg = TembaMessage.create(id=234, contact='C-001', created_on=d0, text="Hello")
            case2 = Case.open(self.unicef, self.user1, [self.pregnancy], self.moh, msg, archive_messages=False)
        with patch.object(timezone, 'now', return_value=d1):
            case2.close(self.user1)

        # case Jan 5th -> Jan 15th
        with patch.object(timezone, 'now', return_value=d0):
            msg = TembaMessage.create(id=345, contact='C-001', created_on=d0, text="Hello")
            case3 = Case.open(self.unicef, self.user1, [self.pregnancy], self.moh, msg, archive_messages=False)
        with patch.object(timezone, 'now', return_value=d2):
            case3.close(self.user1)

        # check no cases open on Jan 4th
        cases = Case.get_open_for_contact_on(self.unicef, 'C-001', datetime(2014, 1, 4, 0, 0, tzinfo=timezone.utc))
        self.assertFalse(cases)

        # check two cases open on Jan 12th
        cases = Case.get_open_for_contact_on(self.unicef, 'C-001', datetime(2014, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(set(cases), {case1, case3})

        # check one case open on Jan 16th
        cases = Case.get_open_for_contact_on(self.unicef, 'C-001', datetime(2014, 1, 16, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(set(cases), {case1})


class CaseCRUDLTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient.get_messages')
    @patch('dash.orgs.models.TembaClient.create_broadcast')
    def test_timeline(self, mock_create_broadcast, mock_get_messages):
        d1 = datetime(2014, 1, 1, 13, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 2, 13, 0, tzinfo=timezone.utc)

        # contact has sent 2 messages, user creates case from the second
        msg1 = TembaMessage.create(id=101, contact='C-001', created_on=d1, text="Hello", direction='I',
                                   labels=[])
        msg2 = TembaMessage.create(id=102, contact='C-001', created_on=d2, text="What is AIDS?", direction='I',
                                   labels=[self.aids])
        mock_get_messages.return_value = [msg2]

        case = Case.open(self.unicef, self.user1, [self.aids], self.moh, msg2, archive_messages=False)

        timeline_url = reverse('cases.case_timeline', args=[case.pk])
        t0 = timezone.now()

        # log in as administrator
        self.login(self.admin)

        # request all of a timeline up to page start time
        response = self.url_get('unicef', '%s?before=%s' % (timeline_url, format_iso8601(t0)))

        self.assertEqual(len(response.json['results']), 2)
        self.assertEqual(response.json['results'][0]['type'], 'M')
        self.assertEqual(response.json['results'][0]['item']['text'], "What is AIDS?")
        self.assertEqual(response.json['results'][0]['item']['contact'], 'C-001')
        self.assertEqual(response.json['results'][0]['item']['direction'], 'I')
        self.assertEqual(response.json['results'][1]['type'], 'A')
        self.assertEqual(response.json['results'][1]['item']['action'], 'O')

        mock_get_messages.assert_called_once_with(contacts=['C-001'], after=d2, before=t0, reverse=True)
        mock_get_messages.reset_mock()

        # page looks for new timeline activity
        t1 = timezone.now()
        response = self.url_get('unicef', '%s?after=%s&before=%s' % (timeline_url, format_iso8601(t0), format_iso8601(t1)))
        self.assertEqual(len(response.json['results']), 0)

        # shouldn't hit the RapidPro API
        self.assertEqual(mock_get_messages.call_count, 0)
        mock_get_messages.reset_mock()

        # another user adds a note
        case.note(self.user2, "Looks interesting")

        # page again looks for new timeline activity
        t2 = timezone.now()
        response = self.url_get('unicef', '%s?after=%s&before=%s' % (timeline_url, format_iso8601(t1), format_iso8601(t2)))

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'A')
        self.assertEqual(response.json['results'][0]['item']['note'], "Looks interesting")

        # still no reason to hit the RapidPro API
        self.assertEqual(mock_get_messages.call_count, 0)
        mock_get_messages.reset_mock()

        # user sends an outgoing message
        d3 = timezone.now()
        mock_create_broadcast.return_value = TembaBroadcast.create(id=201, text="It's bad", urns=[], contacts=['C-001'], created_on=d3)
        Outgoing.create(self.unicef, self.user1, Outgoing.CASE_REPLY, "It's bad", [], ['C-001'], case)

        msg3 = TembaMessage.create(id=103, contact='C-001', created_on=d3, text="It's bad", labels=[], direction='O')
        mock_get_messages.return_value = [msg3]

        # page again looks for new timeline activity
        t3 = timezone.now()
        response = self.url_get('unicef', '%s?after=%s&before=%s' % (timeline_url, format_iso8601(t2), format_iso8601(t3)))

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'M')
        self.assertEqual(response.json['results'][0]['item']['text'], "It's bad")
        self.assertEqual(response.json['results'][0]['item']['direction'], 'O')

        # this time we will have hit the RapidPro API because we know there's a new outgoing message
        mock_get_messages.assert_called_once_with(contacts=['C-001'], after=t2, before=t3, reverse=True)
        mock_get_messages.reset_mock()

        # contact sends a reply
        d4 = timezone.now()
        msg4 = TembaMessage.create(id=104, contact='C-001', created_on=d4, text="OK thanks", labels=[], direction='I')
        case.reply_event(msg4)
        mock_get_messages.return_value = [msg4]

        # page again looks for new timeline activity
        t4 = timezone.now()
        response = self.url_get('unicef', '%s?after=%s&before=%s' % (timeline_url, format_iso8601(t3), format_iso8601(t4)))

        self.assertEqual(len(response.json['results']), 1)
        self.assertEqual(response.json['results'][0]['type'], 'M')
        self.assertEqual(response.json['results'][0]['item']['text'], "OK thanks")
        self.assertEqual(response.json['results'][0]['item']['direction'], 'I')

        # again we will have hit the RapidPro API - this time we know there's a new incoming message
        mock_get_messages.assert_called_once_with(contacts=['C-001'], after=t3, before=t4, reverse=True)
        mock_get_messages.reset_mock()

        # page again looks for new timeline activity
        t5 = timezone.now()
        response = self.url_get('unicef', '%s?after=%s&before=%s' % (timeline_url, format_iso8601(t4), format_iso8601(t5)))

        self.assertEqual(len(response.json['results']), 0)

        # back to having no reason to hit the RapidPro API
        self.assertEqual(mock_get_messages.call_count, 0)


class HomeViewsTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient.get_labels')
    def test_inbox(self, mock_get_labels):
        mock_get_labels.return_value = []

        url = reverse('cases.inbox')

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # log in as regular user
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)


class InitTest(BaseCasesTest):
    def test_safe_max(self):
        self.assertEqual(safe_max(1, 2, 3), 3)
        self.assertEqual(safe_max(None, 2, None), 2)
        self.assertEqual(safe_max(None, None), None)
        self.assertEqual(safe_max(date(2012, 3, 6), date(2012, 5, 2), None), date(2012, 5, 2))

    def test_truncate(self):
        self.assertEqual(truncate("Hello World", 8), "Hello...")
        self.assertEqual(truncate("Hello World", 8, suffix="_"), "Hello W_")
        self.assertEqual(truncate("Hello World", 98), "Hello World")


class LabelTest(BaseCasesTest):
    def test_create(self):
        ebola = Label.create(self.unicef, "Ebola", "Msgs about ebola", ['ebola', 'fever'], [self.moh, self.who])
        self.assertEqual(ebola.org, self.unicef)
        self.assertEqual(ebola.name, "Ebola")
        self.assertEqual(ebola.description, "Msgs about ebola")
        self.assertEqual(ebola.keywords, 'ebola,fever')
        self.assertEqual(ebola.get_keywords(), ['ebola', 'fever'])
        self.assertEqual(set(ebola.get_partners()), {self.moh, self.who})
        self.assertEqual(unicode(ebola), "Ebola")

    def test_get_all(self):
        self.assertEqual(set(Label.get_all(self.unicef)), {self.aids, self.pregnancy})
        self.assertEqual(set(Label.get_all(self.unicef, self.user1)), {self.aids, self.pregnancy})  # MOH user
        self.assertEqual(set(Label.get_all(self.unicef, self.user3)), {self.aids})  # WHO user


class LabelCRUDLTest(BaseCasesTest):
    def test_create(self):
        url = reverse('cases.label_create')

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # submit with no data
        response = self.url_post('unicef', url, dict())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'description', 'This field is required.')

        # submit again with data
        response = self.url_post('unicef', url, dict(name="Ebola", description="Msgs about ebola",
                                                     keywords="ebola,fever", partners=[self.moh.pk, self.who.pk]))
        self.assertEqual(response.status_code, 302)

        ebola = Label.objects.get(name="Ebola")
        self.assertEqual(ebola.org, self.unicef)
        self.assertEqual(ebola.name, "Ebola")
        self.assertEqual(ebola.description, "Msgs about ebola")
        self.assertEqual(ebola.keywords, 'ebola,fever')
        self.assertEqual(ebola.get_keywords(), ['ebola', 'fever'])
        self.assertEqual(set(ebola.get_partners()), {self.moh, self.who})

    def test_list(self):
        url = reverse('cases.label_list')

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['object_list']), [self.aids, self.pregnancy])


class MessageTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient.archive_messages')
    def test_bulk_archive(self, mock_archive_messages):
        Message.bulk_archive(self.unicef, self.user1, [123, 234, 345])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.ARCHIVE)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.messages, [123, 234, 345])

        mock_archive_messages.assert_called_once_with([123, 234, 345])

    def test_annotate_with_sender(self):
        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=timezone.utc)
        Outgoing.objects.create(org=self.unicef, activity='C', broadcast_id=201, recipient_count=1,
                                created_by=self.user2, created_on=d1)
        msg = TembaMessage.create(id=101, broadcast=201, text="Yo")
        Message.annotate_with_sender(self.unicef, [msg])
        self.assertEqual(msg.sender, self.user2)


class OutgoingTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient.create_broadcast')
    def test_create(self, mock_create_broadcast):
        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=timezone.utc)
        mock_create_broadcast.return_value = TembaBroadcast.create(id=1234,
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
        self.assertEqual(outgoing.broadcast_id, 1234)
        self.assertEqual(outgoing.recipient_count, 2)
        self.assertEqual(outgoing.created_by, self.user1)
        self.assertEqual(outgoing.created_on, d1)
        self.assertEqual(outgoing.case, None)


class PartnerTest(BaseCasesTest):
    def test_create(self):
        wfp = Partner.create(self.unicef, "WFP")
        self.assertEqual(wfp.org, self.unicef)
        self.assertEqual(wfp.name, "WFP")
        self.assertEqual(unicode(wfp), "WFP")

        # create some users for this partner
        jim = self.create_user(self.unicef, wfp, ROLE_MANAGER, "Jim", "jim@wfp.org")
        kim = self.create_user(self.unicef, wfp, ROLE_ANALYST, "Kim", "kim@wfp.org")

        self.assertEqual(set(wfp.get_users()), {jim, kim})
        self.assertEqual(set(wfp.get_managers()), {jim})
        self.assertEqual(set(wfp.get_analysts()), {kim})

        # give this partner access to the AIDS and Code labels
        self.aids.partners.add(wfp)
        self.code.partners.add(wfp)

        self.assertEqual(set(wfp.get_labels()), {self.aids, self.code})


class TasksTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient.get_messages')
    @patch('dash.orgs.models.TembaClient.label_messages')
    def test_process_new_unsolicited_task(self, mock_label_messages, mock_get_messages):
        d1 = datetime(2014, 1, 1, 7, 0, tzinfo=timezone.utc)
        d2 = datetime(2014, 1, 1, 8, 0, tzinfo=timezone.utc)
        d3 = datetime(2014, 1, 1, 9, 0, tzinfo=timezone.utc)
        d4 = datetime(2014, 1, 1, 10, 0, tzinfo=timezone.utc)
        d5 = datetime(2014, 1, 1, 11, 0, tzinfo=timezone.utc)
        mock_get_messages.return_value = [
            TembaMessage.create(id=101, contact='C-001', text="What is aids?", created_on=d1),
            TembaMessage.create(id=102, contact='C-002', text="Can I catch Hiv?", created_on=d2),
            TembaMessage.create(id=103, contact='C-003', text="I think I'm pregnant", created_on=d3),
            TembaMessage.create(id=104, contact='C-004', text="Php is amaze", created_on=d4),
            TembaMessage.create(id=105, contact='C-005', text="Thanks for the pregnancy/HIV info", created_on=d5),
        ]
        mock_label_messages.return_value = None

        # contact 5 has a case open that day
        d1 = datetime(2014, 1, 1, 5, 0, tzinfo=timezone.utc)
        with patch.object(timezone, 'now', return_value=d1):
            case1 = Case.objects.create(org=self.unicef, contact_uuid='C-005', assignee=self.moh, message_id=99, message_on=d1)

        process_new_org_unsolicited(self.unicef)

        mock_label_messages.assert_has_calls([call(messages=[101, 102], label='AIDS'),
                                              call(messages=[103], label='Pregnancy')],
                                             any_order=True)

        result = self.unicef.get_task_result(TaskType.label_messages)
        self.assertEqual(result['counts']['messages'], 5)
        self.assertEqual(result['counts']['labels'], 3)

        # check reply event was created for message 5
        events = case1.events.all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, CaseEvent.REPLY)
        self.assertEqual(events[0].created_on, d5)
