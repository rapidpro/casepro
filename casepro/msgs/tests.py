# coding=utf-8
from __future__ import unicode_literals

import pytz
import six

from casepro.cases.models import Case, CaseEvent
from casepro.contacts.models import Contact
from casepro.test import BaseCasesTest
from dash.orgs.models import TaskState
from datetime import datetime
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from django.utils.timezone import now
from mock import patch, call
from temba_client.clients import Pager
from temba_client.utils import format_iso8601
from temba_client.v1.types import Broadcast as TembaBroadcast
from .models import Label, Message, MessageAction, RemoteMessage, Outgoing, MessageExport
from .tasks import handle_messages, pull_messages


class LabelTest(BaseCasesTest):
    @patch('casepro.test.TestBackend.create_label')
    def test_create(self, mock_create_label):
        mock_create_label.return_value = "L-010"

        ebola = Label.create(self.unicef, "Ebola", "Msgs about ebola", ['ebola', 'fever'])
        self.assertEqual(ebola.uuid, 'L-010')
        self.assertEqual(ebola.org, self.unicef)
        self.assertEqual(ebola.name, "Ebola")
        self.assertEqual(ebola.description, "Msgs about ebola")
        self.assertEqual(ebola.keywords, 'ebola,fever')
        self.assertEqual(ebola.get_keywords(), ['ebola', 'fever'])
        self.assertEqual(six.text_type(ebola), "Ebola")

    def test_get_all(self):
        self.assertEqual(set(Label.get_all(self.unicef)), {self.aids, self.pregnancy})
        self.assertEqual(set(Label.get_all(self.unicef, self.user1)), {self.aids, self.pregnancy})  # MOH user
        self.assertEqual(set(Label.get_all(self.unicef, self.user3)), {self.aids})  # WHO user

    def test_get_keyword_map(self):
        self.assertEqual(Label.get_keyword_map(self.unicef), {'aids': self.aids,
                                                              'hiv': self.aids,
                                                              'pregnant': self.pregnancy,
                                                              'pregnancy': self.pregnancy})
        self.assertEqual(Label.get_keyword_map(self.nyaruka), {'java': self.code, 'python': self.code, 'go': self.code})

    def test_release(self):
        self.aids.release()
        self.assertFalse(self.aids.is_active)

    def test_is_valid_keyword(self):
        self.assertTrue(Label.is_valid_keyword('kit'))
        self.assertTrue(Label.is_valid_keyword('kit-kat'))
        self.assertTrue(Label.is_valid_keyword('kit kat'))
        self.assertTrue(Label.is_valid_keyword('kit-kat wrapper'))

        self.assertFalse(Label.is_valid_keyword('it'))  # too short
        self.assertFalse(Label.is_valid_keyword(' kitkat'))  # can't start with a space
        self.assertFalse(Label.is_valid_keyword('-kit'))  # can't start with a dash
        self.assertFalse(Label.is_valid_keyword('kat '))  # can't end with a space
        self.assertFalse(Label.is_valid_keyword('kat-'))  # can't end with a dash


class LabelCRUDLTest(BaseCasesTest):
    @patch('casepro.test.TestBackend.create_label')
    def test_create(self, mock_create_label):
        mock_create_label.return_value = "L-010"

        url = reverse('msgs.label_create')

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # submit with no data
        response = self.url_post('unicef', url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'description', 'This field is required.')

        # submit with name that is reserved
        response = self.url_post('unicef', url, {'name': 'FlaGGED'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', "Reserved label name")

        # submit with name that is invalid
        response = self.url_post('unicef', url, {'name': '+Ebola'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', "Label name cannot start with + or -")

        # submit with a keyword that is too short
        response = self.url_post('unicef', url, {'name': 'Ebola', 'keywords': 'a, ebola'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'keywords', "Keywords must be at least 3 characters long")

        # submit with a keyword that is invalid
        response = self.url_post('unicef', url, {'name': 'Ebola', 'keywords': r'ebol@?, ebola'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'keywords', "Invalid keyword: ebol@?")

        # submit again with valid data
        response = self.url_post('unicef', url, {'name': "Ebola",
                                                 'description': "Msgs about ebola",
                                                 'keywords': "Ebola,fever"})

        self.assertEqual(response.status_code, 302)

        ebola = Label.objects.get(name="Ebola")
        self.assertEqual(ebola.uuid, 'L-010')
        self.assertEqual(ebola.org, self.unicef)
        self.assertEqual(ebola.name, "Ebola")
        self.assertEqual(ebola.description, "Msgs about ebola")
        self.assertEqual(ebola.keywords, 'ebola,fever')
        self.assertEqual(ebola.get_keywords(), ['ebola', 'fever'])

    def test_update(self):
        url = reverse('msgs.label_update', args=[self.pregnancy.pk])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # submit with no data
        response = self.url_post('unicef', url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'description', 'This field is required.')

        # submit again with valid data
        response = self.url_post('unicef', url, {'name': "Pregnancy",
                                                 'description': "Msgs about maternity",
                                                 'keywords': "pregnancy, maternity"})

        self.assertEqual(response.status_code, 302)

        label = Label.objects.get(pk=self.pregnancy.pk)
        self.assertEqual(label.uuid, 'L-002')
        self.assertEqual(label.org, self.unicef)
        self.assertEqual(label.name, "Pregnancy")
        self.assertEqual(label.description, "Msgs about maternity")
        self.assertEqual(label.keywords, 'pregnancy,maternity')
        self.assertEqual(label.get_keywords(), ['pregnancy', 'maternity'])

    def test_list(self):
        url = reverse('msgs.label_list')

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['object_list']), [self.aids, self.pregnancy])

    def test_delete(self):
        url = reverse('msgs.label_delete', args=[self.pregnancy.pk])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_post('unicef', url)
        self.assertEqual(response.status_code, 204)

        pregnancy = Label.objects.get(pk=self.pregnancy.pk)
        self.assertFalse(pregnancy.is_active)


class MessageTest(BaseCasesTest):
    def setUp(self):
        super(MessageTest, self).setUp()

        self.ann = self.create_contact(self.unicef, 'C-001', "Ann")

    def create_test_messages(self):
        self.msg1 = self.create_message(self.unicef, 101, self.ann, "Normal", [self.aids, self.pregnancy])
        self.msg2 = self.create_message(self.unicef, 102, self.ann, "Flow", type='F')
        self.msg3 = self.create_message(self.unicef, 103, self.ann, "Archived", is_archived=True)
        self.msg4 = self.create_message(self.unicef, 104, self.ann, "Flagged", is_flagged=True)
        self.msg5 = self.create_message(self.unicef, 105, self.ann, "Inactive", is_active=False)

    def test_save(self):
        # start with no labels or contacts
        Label.objects.all().delete()
        Contact.objects.all().delete()

        d1 = datetime(2015, 12, 25, 13, 30, 0, 0, pytz.UTC)

        message = Message.objects.create(
            org=self.unicef,
            backend_id=123456789,
            type='I',
            text="I have lots of questions!",
            is_flagged=True,
            is_archived=False,
            created_on=d1,
            __data__contact=("C-001", "Ann"),
            __data__labels=[("L-001", "Spam")]
        )

        ann = Contact.objects.get(org=self.unicef, uuid="C-001", name="Ann")

        self.assertEqual(message.backend_id, 123456789)
        self.assertEqual(message.contact, ann)
        self.assertEqual(message.type, 'I')
        self.assertEqual(message.text, "I have lots of questions!")
        self.assertEqual(message.is_flagged, True)
        self.assertEqual(message.is_archived, False)
        self.assertEqual(message.created_on, d1)

        spam = Label.objects.get(org=self.unicef, uuid="L-001", name="Spam")

        self.assertEqual(set(message.labels.all()), {spam})

        message = Message.objects.select_related('org').prefetch_related('labels').get(backend_id=123456789)

        # check there are no extra db hits when saving without change, assuming appropriate pre-fetches (as above)
        with self.assertNumQueries(1):
            setattr(message, '__data__labels', [("L-001", "Spam")])
            message.save()

        # check removing a group and adding new ones
        with self.assertNumQueries(7):
            setattr(message, '__data__labels', [("L-002", "Feedback"), ("L-003", "Important")])
            message.save()

        message = Message.objects.get(backend_id=123456789)

        feedback = Label.objects.get(org=self.unicef, uuid="L-002", name="Feedback")
        important = Label.objects.get(org=self.unicef, uuid="L-003", name="Important")

        self.assertEqual(set(message.labels.all()), {feedback, important})

    @patch('casepro.test.TestBackend.label_messages')
    @patch('casepro.test.TestBackend.unlabel_messages')
    def test_update_labels(self, mock_unlabel_messages, mock_label_messages):
        self.create_test_messages()
        ebola = self.create_label(self.unicef, "L-007", "Ebola", "About Ebola", "ebola")

        self.msg1.update_labels(self.user1, [self.pregnancy, ebola])

        mock_label_messages.assert_called_once_with(self.unicef, [self.msg1], ebola)
        mock_unlabel_messages.assert_called_once_with(self.unicef, [self.msg1], self.aids)

        actions = list(MessageAction.objects.order_by('pk'))
        self.assertEqual(actions[0].action, MessageAction.LABEL)
        self.assertEqual(actions[0].created_by, self.user1)
        self.assertEqual(actions[0].messages, [101])
        self.assertEqual(actions[0].label, ebola)
        self.assertEqual(actions[1].action, MessageAction.UNLABEL)
        self.assertEqual(actions[1].created_by, self.user1)
        self.assertEqual(actions[1].messages, [101])
        self.assertEqual(actions[1].label, self.aids)

    @patch('casepro.test.TestBackend.flag_messages')
    def test_bulk_flag(self, mock_flag_messages):
        self.create_test_messages()

        Message.bulk_flag(self.unicef, self.user1, [self.msg2, self.msg3])

        mock_flag_messages.assert_called_once_with(self.unicef, [self.msg2, self.msg3])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.FLAG)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.messages, [102, 103])

        self.assertEqual(Message.objects.filter(is_flagged=True).count(), 3)

    @patch('casepro.test.TestBackend.unflag_messages')
    def test_bulk_unflag(self, mock_unflag_messages):
        self.create_test_messages()

        Message.bulk_unflag(self.unicef, self.user1, [self.msg3, self.msg4])

        mock_unflag_messages.assert_called_once_with(self.unicef, [self.msg3, self.msg4])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.UNFLAG)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.messages, [103, 104])

        self.assertEqual(Message.objects.filter(is_flagged=True).count(), 0)

    @patch('casepro.test.TestBackend.label_messages')
    def test_bulk_label(self, mock_label_messages):
        self.create_test_messages()

        Message.bulk_label(self.unicef, self.user1, [self.msg1, self.msg2], self.aids)

        mock_label_messages.assert_called_once_with(self.unicef, [self.msg1, self.msg2], self.aids)

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.LABEL)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.messages, [101, 102])

        self.assertEqual(self.aids.messages.count(), 2)

    @patch('casepro.test.TestBackend.unlabel_messages')
    def test_bulk_unlabel(self, mock_unlabel_messages):
        self.create_test_messages()

        Message.bulk_unlabel(self.unicef, self.user1, [self.msg1, self.msg2], self.aids)

        mock_unlabel_messages.assert_called_once_with(self.unicef, [self.msg1, self.msg2], self.aids)

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.UNLABEL)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.messages, [101, 102])

        self.assertEqual(self.aids.messages.count(), 0)

    @patch('casepro.test.TestBackend.archive_messages')
    def test_bulk_archive(self, mock_archive_messages):
        self.create_test_messages()

        Message.bulk_archive(self.unicef, self.user1, [self.msg1, self.msg2])

        mock_archive_messages.assert_called_once_with(self.unicef, [self.msg1, self.msg2])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.ARCHIVE)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.messages, [101, 102])

        self.assertEqual(Message.objects.filter(is_archived=True).count(), 3)

    @patch('casepro.test.TestBackend.restore_messages')
    def test_bulk_restore(self, mock_restore_messages):
        self.create_test_messages()

        Message.bulk_restore(self.unicef, self.user1, [self.msg2, self.msg3])

        mock_restore_messages.assert_called_once_with(self.unicef, [self.msg2, self.msg3])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.RESTORE)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.messages, [102, 103])

        self.assertEqual(Message.objects.filter(is_archived=True).count(), 0)


class MessageViewsTest(BaseCasesTest):
    @patch('casepro.test.TestBackend.flag_messages')
    @patch('casepro.test.TestBackend.unflag_messages')
    @patch('casepro.test.TestBackend.archive_messages')
    @patch('casepro.test.TestBackend.restore_messages')
    def test_action(self, mock_restore_messages, mock_archive_messages, mock_unflag_messages, mock_flag_messages):
        get_url = lambda action: reverse('msgs.message_action', kwargs={'action': action})

        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        msg1 = self.create_message(self.unicef, 101, ann, "Normal", [self.aids, self.pregnancy])
        msg2 = self.create_message(self.unicef, 102, ann, "Flow", type='F')
        msg3 = self.create_message(self.unicef, 103, ann, "Archived", is_archived=True)

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post('unicef', get_url('flag'), {'messages': "102,103"})

        self.assertEqual(response.status_code, 204)
        mock_flag_messages.assert_called_once_with(self.unicef, [msg2, msg3])
        self.assertEqual(Message.objects.filter(is_flagged=True).count(), 2)

        response = self.url_post('unicef', get_url('unflag'), {'messages': "102,103"})

        self.assertEqual(response.status_code, 204)
        mock_unflag_messages.assert_called_once_with(self.unicef, [msg2, msg3])
        self.assertEqual(Message.objects.filter(is_flagged=True).count(), 0)

        response = self.url_post('unicef', get_url('archive'), {'messages': "102,103"})

        self.assertEqual(response.status_code, 204)
        mock_archive_messages.assert_called_once_with(self.unicef, [msg2, msg3])
        self.assertEqual(Message.objects.filter(is_archived=True).count(), 2)

        response = self.url_post('unicef', get_url('restore'), {'messages': "102,103"})

        self.assertEqual(response.status_code, 204)
        mock_restore_messages.assert_called_once_with(self.unicef, [msg2, msg3])
        self.assertEqual(Message.objects.filter(is_archived=True).count(), 0)

    @patch('casepro.test.TestBackend.label_messages')
    @patch('casepro.test.TestBackend.unlabel_messages')
    def test_label(self, mock_unlabel_messages, mock_label_messages):
        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        msg1 = self.create_message(self.unicef, 101, ann, "Normal", [self.aids])

        url = reverse('msgs.message_label', kwargs={'id': 101})

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post('unicef', url, {'labels': [self.pregnancy.pk]})
        self.assertEqual(response.status_code, 204)

        mock_label_messages.assert_called_once_with(self.unicef, [msg1], self.pregnancy)
        mock_unlabel_messages.assert_called_once_with(self.unicef, [msg1], self.aids)

        msg1.refresh_from_db()
        self.assertEqual(set(msg1.labels.all()), {self.pregnancy})

    @patch('casepro.test.TestBackend.flag_messages')
    @patch('casepro.test.TestBackend.label_messages')
    def test_history(self, mock_label_messages, mock_flag_messages):
        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        msg1 = self.create_message(self.unicef, 101, ann, "Hello")
        msg2 = self.create_message(self.unicef, 102, ann, "Goodbye")

        url = reverse('msgs.message_history', kwargs={'id': 102})

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(len(response.json['actions']), 0)

        Message.bulk_flag(self.unicef, self.user1, [msg1, msg2])
        Message.bulk_label(self.unicef, self.user2, [msg2], self.aids)

        response = self.url_get('unicef', url)
        self.assertEqual(len(response.json['actions']), 2)
        self.assertEqual(response.json['actions'][0]['action'], 'L')
        self.assertEqual(response.json['actions'][0]['created_by']['id'], self.user2.pk)
        self.assertEqual(response.json['actions'][1]['action'], 'F')
        self.assertEqual(response.json['actions'][1]['created_by']['id'], self.user1.pk)

    @patch('dash.orgs.models.TembaClient1.get_messages')
    @patch('dash.orgs.models.TembaClient1.pager')
    def test_search(self, mock_pager, mock_get_messages):
        from temba_client.v1.types import Message as TembaMessage1

        url = reverse('msgs.message_search')

        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        don = self.create_contact(self.unicef, 'C-004', "Don")

        self.create_message(self.unicef, 101, ann, "What is HIV?", [self.aids], is_handled=True)
        self.create_message(self.unicef, 102, bob, "I ♡ RapidPro", is_handled=True)
        self.create_message(self.unicef, 104, don, "RapidCon 2016!", is_handled=True)

        msg1 = TembaMessage1.create(id=101, contact='C-001', text="What is HIV?", created_on=now(), labels=['AIDS'])
        msg2 = TembaMessage1.create(id=102, contact='C-002', text="I ♡ RapidPro", created_on=now(), labels=[])
        msg3 = TembaMessage1.create(id=103, contact='C-003', text="New contact..", created_on=now(), labels=[])
        msg4 = TembaMessage1.create(id=104, contact='C-004', text="RapidCon 2016!", created_on=now(), labels=[])

        pager = Pager(start_page=1)
        mock_pager.return_value = pager
        mock_get_messages.return_value = [msg4, msg3, msg2]

        # log in as a non-administrator
        self.login(self.user1)

        # page requests first page of existing inbox messages
        t0 = now()
        response = self.url_get('unicef', url, {'view': 'inbox', 'text': '', 'label': '', 'page': 1,
                                                'after': '', 'before': format_iso8601(t0)})

        self.assertEqual(len(response.json['results']), 2)  # msg3 doesn't have a local message so hidden for now

        mock_get_messages.assert_called_once_with(archived=False, labels=['AIDS', 'Pregnancy'],
                                                  contacts=None, groups=None, text='', _types=None, direction='I',
                                                  after=None, before=t0, pager=pager)
        mock_get_messages.reset_mock()
        mock_get_messages.return_value = [msg1]

        # page requests next (and last) page of existing inbox messages
        response = self.url_get('unicef', url, {'view': 'inbox', 'text': '', 'label': '', 'page': 2,
                                                'after': '', 'before': format_iso8601(t0)})

        self.assertEqual(len(response.json['results']), 1)

        mock_get_messages.assert_called_once_with(archived=False, labels=['AIDS', 'Pregnancy'],
                                                  contacts=None, groups=None, text='', _types=None, direction='I',
                                                  after=None, before=t0, pager=pager)
        mock_get_messages.reset_mock()
        mock_get_messages.return_value = []

    @patch('dash.orgs.models.TembaClient1.create_broadcast')
    def test_send(self, mock_create_broadcast):
        url = reverse('msgs.message_send')

        # log in as a non-administrator
        self.login(self.user1)

        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=pytz.UTC)
        mock_create_broadcast.return_value = TembaBroadcast.create(id=201,
                                                                   text="That's great",
                                                                   urns=[],
                                                                   contacts=['C-001', 'C-002'],
                                                                   created_on=d1)

        response = self.url_post('unicef', url, {'activity': 'B', 'text': "That's fine",
                                                 'urns': [], 'contacts': ['C-001', 'C-002']})
        outgoing = Outgoing.objects.get(pk=response.json['id'])

        self.assertEqual(outgoing.org, self.unicef)
        self.assertEqual(outgoing.activity, Outgoing.BULK_REPLY)
        self.assertEqual(outgoing.broadcast_id, 201)
        self.assertEqual(outgoing.recipient_count, 2)
        self.assertEqual(outgoing.created_by, self.user1)
        self.assertEqual(outgoing.created_on, d1)
        self.assertEqual(outgoing.case, None)


class OutgoingTest(BaseCasesTest):
    @patch('dash.orgs.models.TembaClient1.create_broadcast')
    def test_create(self, mock_create_broadcast):
        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=pytz.UTC)
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
        from temba_client.v1.types import Message as TembaMessage1

        self.create_contact(self.unicef, 'C-001', None, fields={'nickname': "Bob", 'age': "28", 'state': "WA"})
        self.create_contact(self.unicef, 'C-002', None, fields={'nickname': "Ann", 'age': "32", 'state': "IN"})

        mock_get_messages.return_value = [
            TembaMessage1.create(id=101, contact='C-001', text="What is HIV?", created_on=now(), labels=['AIDS']),
            TembaMessage1.create(id=102, contact='C-002', text="I ♡ RapidPro", created_on=now(), labels=[])
        ]

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post('unicef', '%s?view=inbox&text=&after=2015-04-01T22:00:00.000Z' % reverse('msgs.messageexport_create'))
        self.assertEqual(response.status_code, 200)

        mock_get_messages.assert_called_once_with(archived=False, labels=['AIDS', 'Pregnancy'],
                                                  contacts=None, groups=None, text='', _types=None, direction='I',
                                                  after=datetime(2015, 4, 1, 22, 0, 0, 0, pytz.UTC), before=None,
                                                  pager=None)

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
    @patch('casepro.test.TestBackend.pull_labels')
    @patch('casepro.test.TestBackend.pull_messages')
    def test_pull_messages(self, mock_pull_messages, mock_pull_labels):
        mock_pull_labels.return_value = (1, 2, 3, 4)
        mock_pull_messages.return_value = (5, 6, 7, 8)

        pull_messages(self.unicef.pk)

        task_state = TaskState.objects.get(org=self.unicef, task_key='message-pull')
        self.assertEqual(task_state.get_last_results(), {
            'labels': {'created': 1, 'updated': 2, 'deleted': 3},
            'messages': {'created': 5, 'updated': 6, 'deleted': 7}
        })

    @patch('casepro.test.TestBackend.label_messages')
    @patch('casepro.test.TestBackend.archive_messages')
    def test_handle_messages(self, mock_archive_messages, mock_label_messages):
        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        cat = self.create_contact(self.unicef, 'C-003', "Cat")
        don = self.create_contact(self.unicef, 'C-004', "Don")
        eve = self.create_contact(self.unicef, 'C-005', "Eve")
        fra = self.create_contact(self.unicef, 'C-006', "Fra", is_stub=True)
        nic = self.create_contact(self.nyaruka, 'C-0101', "Nic")

        d1 = datetime(2014, 1, 1, 7, 0, tzinfo=pytz.UTC)
        d2 = datetime(2014, 1, 1, 8, 0, tzinfo=pytz.UTC)
        d3 = datetime(2014, 1, 1, 9, 0, tzinfo=pytz.UTC)
        d4 = datetime(2014, 1, 1, 10, 0, tzinfo=pytz.UTC)
        d5 = datetime(2014, 1, 1, 11, 0, tzinfo=pytz.UTC)

        msg1 = self.create_message(self.unicef, 101, ann, "What is aids?", created_on=d1)
        msg2 = self.create_message(self.unicef, 102, bob, "Can I catch Hiv?", created_on=d2)
        msg3 = self.create_message(self.unicef, 103, cat, "I think I'm pregnant", created_on=d3)
        msg4 = self.create_message(self.unicef, 104, don, "Php is amaze", created_on=d4)
        msg5 = self.create_message(self.unicef, 105, eve, "Thanks for the pregnancy/HIV info", created_on=d5)
        msg6 = self.create_message(self.unicef, 106, fra, "HIV", created_on=d5)
        msg7 = self.create_message(self.nyaruka, 201, nic, "HIV", created_on=d5)

        # contact #5 has a case open that day
        case1 = Case.objects.create(org=self.unicef, contact=eve, assignee=self.moh, message_id=99, message_on=d1)
        case1.opened_on = d1
        case1.save()

        handle_messages(self.unicef.pk)

        self.assertEqual(set(Message.objects.filter(is_handled=True)), {msg1, msg2, msg3, msg4, msg5})
        self.assertEqual(set(Message.objects.filter(is_handled=False)), {msg6, msg7})  # stub contact and wrong org

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
        self.assertEqual(task_state.get_last_results(), {'messages': 5, 'labelled': 3, 'case_replies': 1})

        # check calling again...
        handle_messages(self.unicef.pk)
        task_state = self.unicef.get_task_state('message-handle')
        self.assertEqual(task_state.get_last_results(), {'messages': 0, 'labelled': 0, 'case_replies': 0})


class RemoteMessageTest(BaseCasesTest):
    def test_annotate_with_sender(self):
        from temba_client.v1.types import Message as TembaMessage1

        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=pytz.UTC)
        Outgoing.objects.create(org=self.unicef, activity='C', broadcast_id=201, recipient_count=1,
                                created_by=self.user2, created_on=d1)
        msg = TembaMessage1.create(id=101, broadcast=201, text="Yo")
        RemoteMessage.annotate_with_sender(self.unicef, [msg])
        self.assertEqual(msg.sender, self.user2)

    @patch('dash.orgs.models.TembaClient1.get_messages')
    def test_search(self, mock_get_messages):
        from temba_client.clients import Pager
        from temba_client.v1.types import Message as TembaMessage1

        ann = self.create_contact(self.unicef, 'C-001', "Ann", fields={'nickname': "Ann"})
        bob = self.create_contact(self.unicef, 'C-002', "Bob", fields={'nickname': "Bob"})

        mock_get_messages.return_value = [
            TembaMessage1.create(id=101, contact='C-001', text="What is HIV?", created_on=now(), labels=['AIDS']),
            TembaMessage1.create(id=102, contact='C-002', text="I ♡ RapidPro", created_on=now(), labels=[]),
            TembaMessage1.create(id=103, contact='C-002', text="Yup", created_on=now(), labels=[])
        ]

        self.create_message(self.unicef, 101, ann, "What is HIV?", [self.aids], is_handled=True)
        self.create_message(self.unicef, 102, bob, "I ♡ RapidPro", [self.aids], is_handled=False)

        search = {'labels': ['AIDS'], 'contacts': None, 'groups': None, 'after': None, 'before': None,
                  'text': None, 'types': ['I'], 'archived': False}

        messages = RemoteMessage.search(self.unicef, search, Pager(start_page=1))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].id, 101)
        self.assertEqual(messages[0].text, "What is HIV?")
        self.assertEqual(messages[0].contact, {'uuid': "C-001", 'name': "Ann"})
