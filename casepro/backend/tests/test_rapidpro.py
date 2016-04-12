# coding=utf-8
from __future__ import unicode_literals

import pytz
import time

from dash.orgs.models import Org
from dash.test import MockClientQuery
from datetime import datetime, timedelta
from django.utils.timezone import now
from mock import patch
from temba_client.v1.types import Broadcast as TembaBroadcast
from temba_client.v2.types import Group as TembaGroup, Field as TembaField, Label as TembaLabel, ObjectRef
from temba_client.v2.types import Contact as TembaContact, Message as TembaMessage
from unittest import skip

from casepro.contacts.models import Contact, Field, Group
from casepro.msgs.models import Label, Message
from casepro.test import BaseCasesTest

from ..rapidpro import RapidProBackend, ContactSyncer, MessageSyncer


class ContactSyncerTest(BaseCasesTest):
    syncer = ContactSyncer()

    def test_local_kwargs(self):
        kwargs = self.syncer.local_kwargs(self.unicef, TembaContact.create(
                uuid="C-001",
                name="Bob McFlow",
                language="eng",
                urns=["twitter:bobflow"],
                groups=[ObjectRef.create(uuid="G-001", name="Customers")],
                fields={'age': "34"},
                failed=False,
                blocked=False
        ))

        self.assertEqual(kwargs, {
            'org': self.unicef,
            'uuid': "C-001",
            'name': "Bob McFlow",
            'language': "eng",
            'is_blocked': False,
            'is_stub': False,
            'fields': {'age': "34"},
            '__data__groups': [("G-001", "Customers")],
        })

    def test_update_required(self):
        # create stub contact
        local = Contact.get_or_create(self.unicef, 'C-001', "Ann")

        # a stub contact should always be updated
        self.assertTrue(self.syncer.update_required(local, TembaContact.create(
            uuid='000-001',
            name="Ann",
            urns=['tel:1234'],
            groups=[],
            fields={},
            language=None,
            blocked=False,
            modified_on=now()
        ), {}))

        local.groups.add(self.reporters)
        local.language = "eng"
        local.is_stub = False
        local.fields = {'chat_name': "ann"}
        local.save()

        # no differences (besides null field value which is ignored)
        self.assertFalse(self.syncer.update_required(local, TembaContact.create(
            uuid='000-001',
            name="Ann",
            urns=['tel:1234'],
            groups=[ObjectRef.create(uuid='G-003', name="Reporters")],
            fields={'chat_name': "ann", 'age': None},
            language='eng',
            blocked=False,
            modified_on=now()
        ), {}))

        # name change
        self.assertTrue(self.syncer.update_required(local, TembaContact.create(
            uuid='000-001',
            name="Annie",
            urns=['tel:1234'],
            groups=[ObjectRef.create(uuid='G-003', name="Reporters")],
            fields={'chat_name': "ann"},
            language='eng',
            blocked=False,
            modified_on=now()
        ), {}))

        # group change
        self.assertTrue(self.syncer.update_required(local, TembaContact.create(
            uuid='000-001',
            name="Ann",
            urns=['tel:1234'],
            groups=[ObjectRef.create(uuid='G-002', name="Females")],
            fields={'chat_name': "ann"},
            language='eng',
            blocked=False,
            modified_on=now()
        ), {}))

        # field value change
        self.assertTrue(self.syncer.update_required(local, TembaContact.create(
            uuid='000-001',
            name="Ann",
            urns=['tel:1234'],
            groups=[ObjectRef.create(uuid='G-003', name="Reporters")],
            fields={'chat_name': "ann8111"},
            language='eng',
            blocked=False,
            modified_on=now()
        ), {}))

        # new field
        self.assertTrue(self.syncer.update_required(local, TembaContact.create(
            uuid='000-001',
            name="Ann",
            urns=['tel:1234'],
            groups=[ObjectRef.create(uuid='G-003', name="Reporters")],
            fields={'chat_name': "ann", 'age': "35"},
            language='eng',
            blocked=False,
            modified_on=now()
        ), {}))


class MessageSyncerTest(BaseCasesTest):
    def test_fetch_local(self):
        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        msg = self.create_message(self.unicef, 123456789, ann, "Yes")

        self.assertEqual(MessageSyncer(as_handled=False).fetch_local(self.unicef, 123456789), msg)

    def test_local_kwargs(self):
        d1 = now() - timedelta(hours=1)
        d2 = now() - timedelta(days=32)

        remote = TembaMessage.create(
                id=123456789,
                contact=ObjectRef.create(uuid='C-001', name="Ann"),
                urn="twitter:ann123",
                direction='in',
                type='inbox',
                status='handled',
                visibility='visible',
                text="I have lots of questions!",
                labels=[ObjectRef.create(uuid='L-001', name="Spam"), ObjectRef.create(uuid='L-009', name="Flagged")],
                created_on=d1
        )

        kwargs = MessageSyncer().local_kwargs(self.unicef, remote)

        self.assertEqual(kwargs, {
            'org': self.unicef,
            'backend_id': 123456789,
            'type': 'I',
            'text': "I have lots of questions!",
            'is_flagged': True,
            'is_archived': False,
            'created_on': d1,
            '__data__contact': ("C-001", "Ann"),
            '__data__labels': [("L-001", "Spam")],
        })

        # if remote is archived, so will local
        remote.visibility = 'archived'
        kwargs = MessageSyncer().local_kwargs(self.unicef, remote)
        self.assertEqual(kwargs['is_archived'], True)

        # if syncer is set to save as handled, local will be marked as handled
        kwargs = MessageSyncer(as_handled=True).local_kwargs(self.unicef, remote)
        self.assertTrue(kwargs['is_handled'], True)

        # if remote is too old, local will be marked as handled
        remote.created_on = d2
        kwargs = MessageSyncer(as_handled=False).local_kwargs(self.unicef, remote)
        self.assertTrue(kwargs['is_handled'], True)

        # if remote is deleted, should return none
        remote.visibility = 'deleted'

        self.assertIsNone(MessageSyncer(as_handled=False).local_kwargs(self.unicef, remote))


class RapidProBackendTest(BaseCasesTest):

    def setUp(self):
        super(RapidProBackendTest, self).setUp()

        self.backend = RapidProBackend()
        self.ann = self.create_contact(self.unicef, 'C-001', "Ann")
        self.bob = self.create_contact(self.unicef, 'C-002', "Bob")

    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_pull_contacts(self, mock_get_contacts):
        # start with nothing...
        Group.objects.all().delete()
        Field.objects.all().delete()
        Contact.objects.all().delete()

        mock_get_contacts.side_effect = [
            # first call to get active contacts will return two fetches of 2 and 1 contacts
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001", name="Bob McFlow", language="eng", urns=["twitter:bobflow"],
                        groups=[ObjectRef.create(uuid="G-001", name="Customers")],
                        fields={'age': "34"}, failed=False, blocked=False
                    ),
                    TembaContact.create(
                        uuid="C-002", name="Jim McMsg", language="fre", urns=["tel:+250783835665"],
                        groups=[ObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={'age': "67"}, failed=False, blocked=False
                    ),
                ],
                [
                    TembaContact.create(
                        uuid="C-003", name="Ann McPoll", language="eng", urns=["tel:+250783835664"],
                        groups=[],
                        fields={'age': "35"}, failed=True, blocked=False
                    ),
                ]
            ),
            # second call to get deleted contacts returns a contact we don't have
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-004", name=None, language=None, urns=[], groups=[],
                        fields=None, failed=True, blocked=False
                    ),
                ]
            )
        ]

        with self.assertNumQueries(15):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (3, 0, 0, 0))

        bob = Contact.objects.get(uuid="C-001")
        jim = Contact.objects.get(uuid="C-002")
        ann = Contact.objects.get(uuid="C-003")

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, jim, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), set())

        # stub contact groups will have been created too
        customers = Group.objects.get(org=self.unicef, uuid="G-001", name="Customers", is_active=False)
        spammers = Group.objects.get(org=self.unicef, uuid="G-002", name="Spammers", is_active=False)

        self.assertEqual(bob.name, "Bob McFlow")
        self.assertEqual(bob.language, "eng")
        self.assertEqual(set(bob.groups.all()), {customers})
        self.assertEqual(bob.get_fields(), {'age': "34"})

        mock_get_contacts.side_effect = [
            # first call to get active contacts will just one updated contact
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001", name="Bob McFlough", language="fre", urns=["twitter:bobflow"],
                        groups=[ObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={'age': "35"}, failed=True, blocked=False
                    )
                ]
            ),
            # second call to get deleted contacts returns Jim
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-002", name=None, language=None, urns=[], groups=[],
                        fields=None, failed=True, blocked=False
                    ),
                ]
            )
        ]

        with self.assertNumQueries(12):
            self.assertEqual(self.backend.pull_contacts(self.unicef, None, None), (0, 1, 1, 0))

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), {jim})

        self.assertEqual(jim.groups.count(), 0)  # de-activated contacts are removed from groups

        bob.refresh_from_db()
        self.assertEqual(bob.name, "Bob McFlough")
        self.assertEqual(bob.language, "fre")
        self.assertEqual(set(bob.groups.all()), {spammers})
        self.assertEqual(bob.get_fields(), {'age': "35"})

        mock_get_contacts.side_effect = [
            # first call to get active contacts will return a contact with only a change to URNs.. which we don't track
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001", name="Bob McFlough", language="fre", urns=["twitter:bobflow22"],
                        groups=[ObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={'age': "35"}, failed=True, blocked=False
                    )
                ]
            ),
            MockClientQuery([])
        ]

        with self.assertNumQueries(2):
            self.assertEqual(self.backend.pull_contacts(self.unicef, None, None), (0, 0, 0, 1))

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), {jim})

    @patch('dash.orgs.models.TembaClient2.get_fields')
    def test_pull_fields(self, mock_get_fields):
        # start with no fields
        Field.objects.all().delete()

        mock_get_fields.return_value = MockClientQuery([
            TembaField.create(key="nick_name", label="Nickname", value_type="text"),
            TembaField.create(key="age", label="Age", value_type="numeric"),
        ])

        with self.assertNumQueries(5):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (2, 0, 0, 0))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=True)
        Field.objects.get(key="age", label="Age", value_type="N", is_active=True)

        mock_get_fields.return_value = MockClientQuery([
            TembaField.create(key="age", label="Age (Years)", value_type="numeric"),
            TembaField.create(key="homestate", label="Homestate", value_type="state"),
        ])

        with self.assertNumQueries(6):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (1, 1, 1, 0))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=False)
        Field.objects.get(key="age", label="Age (Years)", value_type="N", is_active=True)
        Field.objects.get(key="homestate", label="Homestate", value_type="S", is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (0, 0, 0, 2))

    @patch('dash.orgs.models.TembaClient2.get_groups')
    def test_pull_groups(self, mock_get_groups):
        # start with no groups
        Group.objects.all().delete()

        mock_get_groups.return_value = MockClientQuery([
            TembaGroup.create(uuid="G-001", name="Customers", count=45),
            TembaGroup.create(uuid="G-002", name="Developers", count=32),
        ])

        with self.assertNumQueries(5):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (2, 0, 0, 0))

        Group.objects.get(uuid="G-001", name="Customers", count=45, is_active=True)
        Group.objects.get(uuid="G-002", name="Developers", count=32, is_active=True)

        mock_get_groups.return_value = MockClientQuery([
            TembaGroup.create(uuid="G-002", name="Devs", count=32),
            TembaGroup.create(uuid="G-003", name="Spammers", count=13),
        ])

        with self.assertNumQueries(6):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (1, 1, 1, 0))

        Group.objects.get(uuid="G-001", name="Customers", count=45, is_active=False)
        Group.objects.get(uuid="G-002", name="Devs", count=32, is_active=True)
        Group.objects.get(uuid="G-003", name="Spammers", count=13, is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (0, 0, 0, 2))

    @patch('dash.orgs.models.TembaClient2.get_labels')
    def test_pull_labels(self, mock_get_labels):
        # start with no labels
        Label.objects.all().delete()

        mock_get_labels.return_value = MockClientQuery([
            TembaLabel.create(uuid="L-001", name="Requests", count=45),
            TembaLabel.create(uuid="L-002", name="Feedback", count=32),
            TembaLabel.create(uuid="L-009", name="Flagged", count=21),  # should be ignored
        ])

        self.unicef = Org.objects.prefetch_related('labels').get(pk=self.unicef.pk)

        with self.assertNumQueries(6):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (2, 0, 0, 1))

        Label.objects.get(uuid="L-001", name="Requests", is_active=True)
        Label.objects.get(uuid="L-002", name="Feedback", is_active=True)

        self.assertEqual(Label.objects.filter(name="Flagged").count(), 0)

        mock_get_labels.return_value = MockClientQuery([
            TembaLabel.create(uuid="L-002", name="Complaints", count=32),
            TembaLabel.create(uuid="L-003", name="Spam", count=13),
        ])

        with self.assertNumQueries(6):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (1, 1, 1, 0))

        Label.objects.get(uuid="L-001", name="Requests", is_active=False)
        Label.objects.get(uuid="L-002", name="Complaints", is_active=True)
        Label.objects.get(uuid="L-003", name="Spam", is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (0, 0, 0, 2))

    @patch('dash.orgs.models.TembaClient2.get_messages')
    def test_pull_messages(self, mock_get_messages):
        d1 = now() - timedelta(hours=10)
        d2 = now() - timedelta(hours=9)
        d3 = now() - timedelta(hours=8)
        d4 = now() - timedelta(hours=7)
        d5 = now() - timedelta(hours=6)

        mock_get_messages.side_effect = [
            MockClientQuery([
                TembaMessage.create(id=101,
                                    contact=ObjectRef.create(uuid='C-001', name="Ann"),
                                    type='inbox',
                                    text="What is aids?",
                                    visibility="visible",
                                    labels=[
                                        ObjectRef.create(uuid='L-001', name="AIDS"),  # existing label
                                        ObjectRef.create(uuid='L-009', name="Flagged"),  # pseudo-label
                                    ],
                                    created_on=d1),
                TembaMessage.create(id=102,
                                    contact=ObjectRef.create(uuid='C-002', name="Bob"),
                                    type='inbox',
                                    text="Can I catch Hiv?",
                                    visibility="visible",
                                    labels=[
                                        ObjectRef.create(uuid='L-007', name="Important"),  # new label
                                    ],
                                    created_on=d2),
                TembaMessage.create(id=103,
                                    contact=ObjectRef.create(uuid='C-003', name="Cat"),
                                    type='inbox',
                                    text="I think I'm pregnant",
                                    visibility="visible",
                                    labels=[],
                                    created_on=d3),
                TembaMessage.create(id=104,
                                    contact=ObjectRef.create(uuid='C-004', name="Don"),
                                    type='flow',
                                    text="Php is amaze",
                                    visibility="visible",
                                    labels=[],
                                    created_on=d4),
                TembaMessage.create(id=105,
                                    contact=ObjectRef.create(uuid='C-005', name="Eve"),
                                    type='flow',
                                    text="Thanks for the pregnancy/HIV info",
                                    visibility="visible",
                                    labels=[],
                                    created_on=d5)
            ])
        ]

        self.assertEqual(self.backend.pull_messages(self.unicef, d1, d5), (5, 0, 0, 0))

        self.assertEqual(Contact.objects.filter(is_stub=False).count(), 2)
        self.assertEqual(Contact.objects.filter(is_stub=True).count(), 3)
        self.assertEqual(Message.objects.filter(is_handled=False).count(), 5)

        msg1 = Message.objects.get(backend_id=101, type='I', text="What is aids?", is_archived=False, is_flagged=True)
        important = Label.objects.get(org=self.unicef, uuid='L-007', name="Important")

        self.assertEqual(set(msg1.labels.all()), {self.aids})

        # a message is updated in RapidPro
        mock_get_messages.side_effect = [
            MockClientQuery([
                TembaMessage.create(id=101,
                                    contact=ObjectRef.create(uuid='C-001', name="Ann"),
                                    type='inbox',
                                    text="What is aids?",
                                    visibility="archived",
                                    labels=[
                                        ObjectRef.create(uuid='L-001', name="AIDS"),
                                        ObjectRef.create(uuid='L-007', name="Important")
                                    ],
                                    created_on=d1)
            ])
        ]

        self.assertEqual(self.backend.pull_messages(self.unicef, d1, d5), (0, 1, 0, 0))

        msg1 = Message.objects.get(backend_id=101, type='I', text="What is aids?", is_archived=True, is_flagged=False)

        self.assertEqual(set(msg1.labels.all()), {self.aids, important})

    @patch('dash.orgs.models.TembaClient1.create_label')
    @patch('dash.orgs.models.TembaClient1.get_labels')
    def test_create_label(self, mock_get_labels, mock_create_label):
        mock_get_labels.return_value = [
            TembaLabel.create(uuid="L-011", name="Not Ebola", count=213),
            TembaLabel.create(uuid="L-012", name="ebola", count=345)
        ]

        # check when label exists
        self.assertEqual(self.backend.create_label(self.unicef, "Ebola"), "L-012")

        mock_create_label.assert_not_called()

        # check when label doesn't exist
        mock_get_labels.return_value = []
        mock_create_label.return_value = TembaLabel.create(uuid='L-013', name="Ebola", count=0)

        self.assertEqual(self.backend.create_label(self.unicef, "Ebola"), "L-013")

        mock_create_label.assert_called_once_with(name="Ebola")

    @patch('dash.orgs.models.TembaClient1.create_broadcast')
    def test_create_outgoing(self, mock_create_broadcast):
        d1 = datetime(2014, 1, 2, 6, 0, tzinfo=pytz.UTC)
        mock_create_broadcast.return_value = TembaBroadcast.create(id=201,
                                                                   text="That's great",
                                                                   urns=["tel:+250783935665"],
                                                                   contacts=["C-001"],
                                                                   created_on=d1)

        res = self.backend.create_outgoing(self.unicef, "That's great", [self.ann], ["tel:+250783935665"])

        self.assertEqual(res, (201, d1))
        mock_create_broadcast.assert_called_once_with(text="That's great", contacts=["C-001"],
                                                      urns=["tel:+250783935665"])

    @patch('dash.orgs.models.TembaClient1.add_contacts')
    def test_add_to_group(self, mock_add_contacts):
        self.backend.add_to_group(self.unicef, self.bob, self.reporters)

        mock_add_contacts.assert_called_once_with(['C-002'], group_uuid='G-003')

    @patch('dash.orgs.models.TembaClient1.remove_contacts')
    def test_remove_from_group(self, mock_remove_contacts):
        self.backend.remove_from_group(self.unicef, self.bob, self.reporters)

        mock_remove_contacts.assert_called_once_with(['C-002'], group_uuid='G-003')

    @patch('dash.orgs.models.TembaClient1.expire_contacts')
    def test_stop_runs(self, mock_expire_contacts):
        self.backend.stop_runs(self.unicef, self.bob)

        mock_expire_contacts.assert_called_once_with(contacts=['C-002'])

    @patch('dash.orgs.models.TembaClient1.label_messages')
    def test_label_messages(self, mock_label_messages):
        # empty message list shouldn't make API call
        self.backend.label_messages(self.unicef, [], self.aids)

        mock_label_messages.assert_not_called()

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.label_messages(self.unicef, [msg1, msg2], self.aids)

        mock_label_messages.assert_called_once_with(messages=[123, 234], label_uuid='L-001')

    @patch('dash.orgs.models.TembaClient1.unlabel_messages')
    def test_unlabel_messages(self, mock_unlabel_messages):
        # empty message list shouldn't make API call
        self.backend.unlabel_messages(self.unicef, [], self.aids)

        mock_unlabel_messages.assert_not_called()

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.unlabel_messages(self.unicef, [msg1, msg2], self.aids)

        mock_unlabel_messages.assert_called_once_with(messages=[123, 234], label_uuid='L-001')

    @patch('dash.orgs.models.TembaClient1.archive_messages')
    def test_archive_messages(self, mock_archive_messages):
        # empty message list shouldn't make API call
        self.backend.archive_messages(self.unicef, [])

        mock_archive_messages.assert_not_called()

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.archive_messages(self.unicef, [msg1, msg2])

        mock_archive_messages.assert_called_once_with(messages=[123, 234])

    @patch('dash.orgs.models.TembaClient1.archive_contacts')
    def test_archive_contact_messages(self, mock_archive_contacts):
        self.backend.archive_contact_messages(self.unicef, self.bob)

        mock_archive_contacts.assert_called_once_with(contacts=['C-002'])

    @patch('dash.orgs.models.TembaClient1.unarchive_messages')
    def test_restore_messages(self, mock_unarchive_messages):
        # empty message list shouldn't make API call
        self.backend.restore_messages(self.unicef, [])

        mock_unarchive_messages.assert_not_called()

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.restore_messages(self.unicef, [msg1, msg2])

        mock_unarchive_messages.assert_called_once_with(messages=[123, 234])

    @patch('dash.orgs.models.TembaClient1.label_messages')
    def test_flag_messages(self, mock_label_messages):
        # empty message list shouldn't make API call
        self.backend.flag_messages(self.unicef, [])

        mock_label_messages.assert_not_called()

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.flag_messages(self.unicef, [msg1, msg2])

        mock_label_messages.assert_called_once_with(messages=[123, 234], label='Flagged')

    @patch('dash.orgs.models.TembaClient1.unlabel_messages')
    def test_unflag_messages(self, mock_unlabel_messages):
        # empty message list shouldn't make API call
        self.backend.unflag_messages(self.unicef, [])

        mock_unlabel_messages.assert_not_called()

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.unflag_messages(self.unicef, [msg1, msg2])

        mock_unlabel_messages.assert_called_once_with(messages=[123, 234], label='Flagged')

    @patch('dash.orgs.models.TembaClient2.get_messages')
    def test_fetch_contact_messages(self, mock_get_messages):
        d1 = datetime(2015, 1, 2, 13, 0, tzinfo=pytz.UTC)
        d2 = datetime(2015, 1, 2, 14, 0, tzinfo=pytz.UTC)
        d3 = datetime(2015, 1, 2, 15, 0, tzinfo=pytz.UTC)

        mock_get_messages.return_value = MockClientQuery([
            TembaMessage.create(
                id=101,
                broadcast=201,
                contact=ObjectRef.create(uuid="C-001", name="Ann"),
                text="What is AIDS?",
                type='inbox',
                direction='in',
                visibility='visible',
                labels=[ObjectRef.create(uuid="L-001", name="AIDS"), ObjectRef.create(uuid="L-111", name="Flagged")],
                created_on=d2
            )
        ])

        messages = self.backend.fetch_contact_messages(self.unicef, self.ann, d1, d3)

        self.assertEqual(messages, [{
            'id': 101,
            'contact': {'uuid': "C-001", 'name': "Ann"},
            'text': "What is AIDS?",
            'time': d2,
            'labels': [{'id': self.aids.pk, 'name': "AIDS"}],
            'flagged': True,
            'archived': False,
            'direction': 'I',
            'flow': False,
            'sender': None,
            'broadcast': 201
        }])


@skip
class PerfTest(BaseCasesTest):

    def setUp(self):
        super(PerfTest, self).setUp()

        self.backend = RapidProBackend()

    @patch('dash.orgs.models.TembaClient2.get_contacts')
    @patch('dash.orgs.models.TembaClient2.get_fields')
    @patch('dash.orgs.models.TembaClient2.get_groups')
    # @override_settings(DEBUG=True)
    def test_contact_sync(self, mock_get_groups, mock_get_fields, mock_get_contacts):
        # start with no groups or fields
        Group.objects.all().delete()
        Field.objects.all().delete()

        fetch_size = 250
        num_fetches = 4
        num_groups = 50
        num_fields = 50
        names = ["Ann", "Bob", "Cat"]
        field_values = ["12345", None]
        groups_in = 5

        # setup get_fields
        fields = [TembaField.create(key='field_%d' % f, label='Field #%d' % f, value_type='text')
                  for f in range(0, num_fields)]
        mock_get_fields.return_value = MockClientQuery(fields)

        # sync fields
        start = time.time()
        self.assertEqual((num_fields, 0, 0, 0), self.backend.pull_fields(self.unicef))

        print "Initial field sync: %f secs" % (time.time() - start)

        # setup get_groups
        groups = [TembaGroup.create(uuid="G0000000-0000-0000-0000-00000000%04d" % g, name="Group #%d" % g, count=0)
                  for g in range(0, num_groups)]
        mock_get_groups.return_value = MockClientQuery(groups)

        # sync groups
        start = time.time()
        self.assertEqual((num_groups, 0, 0, 0), self.backend.pull_groups(self.unicef))

        print "Initial group sync: %f secs" % (time.time() - start)

        # setup get_contacts to return multiple fetches of contacts
        active_fetches = []
        for b in range(0, num_fetches):
            batch = []
            for c in range(0, fetch_size):
                num = b * fetch_size + c
                batch.append(TembaContact.create(
                    uuid="C0000000-0000-0000-0000-00000000%04d" % num,
                    name=names[num % len(names)],
                    language="eng",
                    urns=["tel:+26096415%04d" % num],
                    groups=[
                        ObjectRef.create(uuid="G0000000-0000-0000-0000-00000000%04d" % g, name="Group #%d" % g)
                        for g in range(0, groups_in)
                    ],
                    fields={'custom_field_%d' % f: field_values[f % len(field_values)] for f in range(0, num_fields)},
                    failed=False,
                    blocked=False
                ))
            active_fetches.append(batch)

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]  # no deleted contacts

        start = time.time()
        num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)

        print "Initial contact sync: %f secs" % (time.time() - start)

        self.assertEqual((num_created, num_updated, num_deleted), (num_fetches * fetch_size, 0, 0))

        # slowest_queries = sorted(connection.queries, key=lambda q: q['time'], reverse=True)[:10]

        # for q in slowest_queries:
        #    print "%s -- %s" % (q['time'], q['sql'])

        # simulate a subsequent sync with no changes
        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

        print "Contact sync with no changes: %f secs" % (time.time() - start)

        # simulate an update of 1 field value
        for batch in active_fetches:
            for c in batch:
                c.fields['custom_field_1'] = "UPDATED"

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, num_fetches * fetch_size, 0))

        print "Contact sync with 1 field value changes: %f secs" % (time.time() - start)

        # simulate an update of 10 field values
        for batch in active_fetches:
            for c in batch:
                for f in (10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                    c.fields['custom_field_%d' % f] = "UPDATED"

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, num_fetches * fetch_size, 0))

        print "Contact sync with 10 field value changes: %f secs" % (time.time() - start)
