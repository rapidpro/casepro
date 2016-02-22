# coding=utf-8
from __future__ import unicode_literals

import pytz
import time

from casepro.contacts.models import Contact, Field, Group
from casepro.msgs.models import Label, Message
from casepro.test import BaseCasesTest
from dash.test import MockClientQuery
from datetime import datetime
from django.utils.timezone import now
from mock import patch
from temba_client.v2.types import Group as TembaGroup, Field as TembaField, Label as TembaLabel, ObjectRef
from temba_client.v2.types import Contact as TembaContact, Message as TembaMessage
from unittest import skip
from ..rapidpro import RapidProBackend


class RapidProBackendTest(BaseCasesTest):

    def setUp(self):
        super(RapidProBackendTest, self).setUp()

        self.backend = RapidProBackend()
        self.ann = self.create_contact(self.unicef, 'C-001', "Ann")
        self.bob = self.create_contact(self.unicef, 'C-002', "Bob")

    @patch('dash.orgs.models.TembaClient2.get_fields')
    def test_pull_fields(self, mock_get_fields):
        # start with no fields
        Field.objects.all().delete()

        mock_get_fields.return_value = MockClientQuery([
            TembaField.create(key="nick_name", label="Nickname", value_type="text"),
            TembaField.create(key="age", label="Age", value_type="numeric"),
        ])

        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (2, 0, 0))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=True)
        Field.objects.get(key="age", label="Age", value_type="N", is_active=True)

        mock_get_fields.return_value = MockClientQuery([
            TembaField.create(key="age", label="Age (Years)", value_type="numeric"),
            TembaField.create(key="homestate", label="Homestate", value_type="state"),
        ])

        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (1, 1, 1))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=False)
        Field.objects.get(key="age", label="Age (Years)", value_type="N", is_active=True)
        Field.objects.get(key="homestate", label="Homestate", value_type="S", is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(1):
            num_created, num_updated, num_deleted = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

    @patch('dash.orgs.models.TembaClient2.get_groups')
    def test_pull_groups(self, mock_get_groups):
        # start with no groups
        Group.objects.all().delete()

        mock_get_groups.return_value = MockClientQuery([
            TembaGroup.create(uuid="G-001", name="Customers", count=45),
            TembaGroup.create(uuid="G-002", name="Developers", count=32),
        ])

        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (2, 0, 0))

        Group.objects.get(uuid="G-001", name="Customers", count=45, is_active=True)
        Group.objects.get(uuid="G-002", name="Developers", count=32, is_active=True)

        mock_get_groups.return_value = MockClientQuery([
            TembaGroup.create(uuid="G-002", name="Devs", count=32),
            TembaGroup.create(uuid="G-003", name="Spammers", count=13),
        ])

        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (1, 1, 1))

        Group.objects.get(uuid="G-001", name="Customers", count=45, is_active=False)
        Group.objects.get(uuid="G-002", name="Devs", count=32, is_active=True)
        Group.objects.get(uuid="G-003", name="Spammers", count=13, is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(1):
            num_created, num_updated, num_deleted = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

    @patch('dash.orgs.models.TembaClient2.get_labels')
    def test_pull_labels(self, mock_get_labels):
        # start with no labels
        Label.objects.all().delete()

        mock_get_labels.return_value = MockClientQuery([
            TembaLabel.create(uuid="L-001", name="Requests", count=45),
            TembaLabel.create(uuid="L-002", name="Feedback", count=32),
        ])

        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (2, 0, 0))

        Label.objects.get(uuid="L-001", name="Requests", is_active=True)
        Label.objects.get(uuid="L-002", name="Feedback", is_active=True)

        mock_get_labels.return_value = MockClientQuery([
            TembaLabel.create(uuid="L-002", name="Complaints", count=32),
            TembaLabel.create(uuid="L-003", name="Spam", count=13),
        ])

        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (1, 1, 1))

        Label.objects.get(uuid="L-001", name="Requests", is_active=False)
        Label.objects.get(uuid="L-002", name="Complaints", is_active=True)
        Label.objects.get(uuid="L-003", name="Spam", is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(1):
            num_created, num_updated, num_deleted = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

    @patch('dash.orgs.models.TembaClient2.get_messages')
    def test_pull_messages(self, mock_get_messages):
        d1 = datetime(2014, 1, 1, 7, 0, tzinfo=pytz.UTC)
        d2 = datetime(2014, 1, 1, 8, 0, tzinfo=pytz.UTC)
        d3 = datetime(2014, 1, 1, 9, 0, tzinfo=pytz.UTC)
        d4 = datetime(2014, 1, 1, 10, 0, tzinfo=pytz.UTC)
        d5 = datetime(2014, 1, 1, 11, 0, tzinfo=pytz.UTC)

        mock_get_messages.side_effect = [
            MockClientQuery([
                TembaMessage.create(id=101, contact=ObjectRef.create(uuid='C-001', name="Ann"),
                                    text="What is aids?", created_on=d1),
                TembaMessage.create(id=102, contact=ObjectRef.create(uuid='C-002', name="Bob"),
                                    text="Can I catch Hiv?", created_on=d2),
                TembaMessage.create(id=103, contact=ObjectRef.create(uuid='C-003', name="Cat"),
                                    text="I think I'm pregnant", created_on=d3),
                TembaMessage.create(id=104, contact=ObjectRef.create(uuid='C-004', name="Don"),
                                    text="Php is amaze", created_on=d4),
                TembaMessage.create(id=105, contact=ObjectRef.create(uuid='C-005', name="Eve"),
                                    text="Thanks for the pregnancy/HIV info", created_on=d5)
            ])
        ]

        self.backend.pull_messages(self.unicef, d1, d5)

        self.assertEqual(Contact.objects.filter(is_stub=False).count(), 2)
        self.assertEqual(Contact.objects.filter(is_stub=True).count(), 3)
        self.assertEqual(Message.objects.filter(is_handled=False).count(), 5)

    @patch('dash.orgs.models.TembaClient1.create_label')
    @patch('dash.orgs.models.TembaClient1.get_labels')
    def test_create_label(self, mock_get_labels, mock_create_label):
        mock_get_labels.return_value = [
            TembaLabel.create(uuid='L-011', name='Not Ebola', count=213),
            TembaLabel.create(uuid='L-012', name='ebola', count=345)
        ]

        # check when label exists
        self.assertEqual(self.backend.create_label(self.unicef, "Ebola"), 'L-012')

        # check when label doesn't exist
        mock_get_labels.return_value = []
        mock_create_label.return_value = TembaLabel.create(uuid='L-013', name='Ebola', count=0)

        self.assertEqual(self.backend.create_label(self.unicef, "Ebola"), 'L-013')

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

        mock_expire_contacts.assert_called_once_with(['C-002'])

    @patch('dash.orgs.models.TembaClient1.label_messages')
    def test_label_messages(self, mock_label_messages):
        # empty message list shouldn't make API call
        self.backend.label_messages(self.unicef, [], self.aids)

        mock_label_messages.assert_not_called()

        msg1 = Message.objects.create(org=self.unicef, backend_id=123, contact=self.bob, text="Hello", type="I", created_on=now())
        msg2 = Message.objects.create(org=self.unicef, backend_id=234, contact=self.bob, text="Goodbye", type="I", created_on=now())

        self.backend.label_messages(self.unicef, [msg1, msg2], self.aids)

        mock_label_messages.assert_called_once_with(messages=[123, 234], label_uuid='L-001')

    @patch('dash.orgs.models.TembaClient1.archive_messages')
    def test_archive_messages(self, mock_archive_messages):
        # empty message list shouldn't make API call
        self.backend.archive_messages(self.unicef, [])

        mock_archive_messages.assert_not_called()

        msg1 = Message.objects.create(org=self.unicef, backend_id=123, contact=self.bob, text="Hello", type="I", created_on=now())
        msg2 = Message.objects.create(org=self.unicef, backend_id=234, contact=self.bob, text="Goodbye", type="I", created_on=now())

        self.backend.archive_messages(self.unicef, [msg1, msg2])

        mock_archive_messages.assert_called_once_with(messages=[123, 234])

    @patch('dash.orgs.models.TembaClient1.get_messages')
    @patch('dash.orgs.models.TembaClient1.archive_messages')
    def test_archive_contact_messages(self, mock_archive_messages, mock_get_messages):
        from temba_client.v1.types import Message as TembaMessage1

        mock_get_messages.return_value = [TembaMessage1.create(id=123), TembaMessage1.create(id=234)]

        self.backend.archive_contact_messages(self.unicef, self.bob)

        mock_get_messages.assert_called_once_with(contacts=['C-002'], direction='I', statuses=['H'], _types=['I'], archived=False)
        mock_archive_messages.assert_called_once_with(messages=[123, 234])


@skip
class PerfTest(BaseCasesTest):

    def setUp(self):
        super(PerfTest, self).setUp()

        self.backend = RapidProBackend()

    @patch('dash.orgs.models.TembaClient2.get_contacts')
    @patch('dash.orgs.models.TembaClient2.get_fields')
    @patch('dash.orgs.models.TembaClient2.get_groups')
    # @override_settings(DEBUG=True)
    def test_sync(self, mock_get_groups, mock_get_fields, mock_get_contacts):
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
        self.assertEqual((num_fields, 0, 0), self.backend.pull_fields(self.unicef))

        # setup get_groups
        groups = [TembaGroup.create(uuid="G0000000-0000-0000-0000-00000000%04d" % g, name="Group #%d" % g, count=0)
                  for g in range(0, num_groups)]
        mock_get_groups.return_value = MockClientQuery(groups)

        # sync groups
        self.assertEqual((num_groups, 0, 0), self.backend.pull_groups(self.unicef))

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
        num_created, num_updated, num_deleted = self.backend.pull_contacts(self.unicef, None, None)

        print "Initial contact sync: %f secs" % (time.time() - start)

        self.assertEqual((num_created, num_updated, num_deleted), (num_fetches * fetch_size, 0, 0))

        # slowest_queries = sorted(connection.queries, key=lambda q: q['time'], reverse=True)[:10]

        # for q in slowest_queries:
        #    print "%s -- %s" % (q['time'], q['sql'])

        # simulate a subsequent sync with no changes
        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

        print "Contact sync with no changes: %f secs" % (time.time() - start)

        # simulate an update of 1 field value
        for batch in active_fetches:
            for c in batch:
                c.fields['custom_field_1'] = "UPDATED"

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, num_fetches * fetch_size, 0))

        print "Contact sync with 1 field value changes: %f secs" % (time.time() - start)

        # simulate an update of 10 field values
        for batch in active_fetches:
            for c in batch:
                for f in (10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                    c.fields['custom_field_%d' % f] = "UPDATED"

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, num_fetches * fetch_size, 0))

        print "Contact sync with 10 field value changes: %f secs" % (time.time() - start)
