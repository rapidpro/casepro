# coding=utf-8
from __future__ import unicode_literals

import time

from casepro.contacts.models import Contact, Group, Field
from casepro.test import BaseCasesTest
from dash.test import MockClientQuery
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from mock import patch
from temba_client.v2.types import Group as TembaGroup, Field as TembaField
from temba_client.v2.types import Contact as TembaContact, ObjectRef as TembaObjectRef
from unittest import skip
from .sync import sync_pull_groups, sync_pull_fields, sync_pull_contacts, temba_compare_contacts, temba_merge_contacts


class SyncTest(BaseCasesTest):

    @patch('dash.orgs.models.TembaClient2.get_groups')
    def test_sync_pull_groups(self, mock_get_groups):
        # start with no groups
        Group.objects.all().delete()

        mock_get_groups.return_value = MockClientQuery([
            TembaGroup.create(uuid="G-001", name="Customers", count=45),
            TembaGroup.create(uuid="G-002", name="Developers", count=32),
        ])

        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted = sync_pull_groups(self.unicef, Group)

        self.assertEqual((num_created, num_updated, num_deleted), (2, 0, 0))

        Group.objects.get(uuid="G-001", name="Customers", count=45, is_active=True)
        Group.objects.get(uuid="G-002", name="Developers", count=32, is_active=True)

        mock_get_groups.return_value = MockClientQuery([
            TembaGroup.create(uuid="G-002", name="Devs", count=32),
            TembaGroup.create(uuid="G-003", name="Spammers", count=13),
        ])

        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted = sync_pull_groups(self.unicef, Group)

        self.assertEqual((num_created, num_updated, num_deleted), (1, 1, 1))

        Group.objects.get(uuid="G-001", name="Customers", count=45, is_active=False)
        Group.objects.get(uuid="G-002", name="Devs", count=32, is_active=True)
        Group.objects.get(uuid="G-003", name="Spammers", count=13, is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(1):
            num_created, num_updated, num_deleted = sync_pull_groups(self.unicef, Group)

        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

    @patch('dash.orgs.models.TembaClient2.get_fields')
    def test_sync_pull_fields(self, mock_get_fields):
        # start with no fields
        Field.objects.all().delete()

        mock_get_fields.return_value = MockClientQuery([
            TembaField.create(key="nick_name", label="Nickname", value_type="text"),
            TembaField.create(key="age", label="Age", value_type="numeric"),
        ])

        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted = sync_pull_fields(self.unicef, Field)

        self.assertEqual((num_created, num_updated, num_deleted), (2, 0, 0))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=True)
        Field.objects.get(key="age", label="Age", value_type="N", is_active=True)

        mock_get_fields.return_value = MockClientQuery([
            TembaField.create(key="age", label="Age (Years)", value_type="numeric"),
            TembaField.create(key="homestate", label="Homestate", value_type="state"),
        ])

        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted = sync_pull_fields(self.unicef, Field)

        self.assertEqual((num_created, num_updated, num_deleted), (1, 1, 1))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=False)
        Field.objects.get(key="age", label="Age (Years)", value_type="N", is_active=True)
        Field.objects.get(key="homestate", label="Homestate", value_type="S", is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(1):
            num_created, num_updated, num_deleted = sync_pull_fields(self.unicef, Field)

        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_sync_pull_contacts(self, mock_get_contacts):
        # start with no groups or fields
        Group.objects.all().delete()
        Field.objects.all().delete()

        mock_get_contacts.side_effect = [
            # first call to get active contacts will return two fetches of 2 and 1 contacts
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001", name="Bob McFlow", language="eng", urns=["twitter:bobflow"],
                        groups=[TembaObjectRef.create(uuid="G-001", name="Customers")],
                        fields={'age': "34"}, failed=False, blocked=False
                    ),
                    TembaContact.create(
                        uuid="C-002", name="Jim McMsg", language="fre", urns=["tel:+250783835665"],
                        groups=[TembaObjectRef.create(uuid="G-002", name="Spammers")],
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

        with self.assertNumQueries(25):
            num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact, inc_urns=False,
                                                                       prefetch_related=('groups', 'values__field'))

        self.assertEqual((num_created, num_updated, num_deleted), (3, 0, 0))

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
                        groups=[TembaObjectRef.create(uuid="G-002", name="Spammers")],
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
            num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact, inc_urns=False,
                                                                       prefetch_related=('groups', 'values__field'))

        self.assertEqual((num_created, num_updated, num_deleted), (0, 1, 1))

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), {jim})

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
                        groups=[TembaObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={'age': "35"}, failed=True, blocked=False
                    )
                ]
            ),
            MockClientQuery([])
        ]

        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact, inc_urns=False,
                                                                       prefetch_related=('groups', 'values__field'))
        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), {jim})

        mock_get_contacts.side_effect = [
            # first call to get active contacts will show one contact is now blocked
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001", name="Bob McFlough", language="fre", urns=["twitter:bobflow"],
                        groups=[TembaObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={'age': 35}, failed=True, blocked=True
                    )
                ]
            ),
            MockClientQuery([])
        ]

        with self.assertNumQueries(5):
            num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact,
                                                                       prefetch_related=('groups', 'values__field'))

        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 1))  # blocked = deleted for us

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), {bob, jim})

    def test_temba_compare_contacts(self):
        group1 = TembaObjectRef.create(uuid='000-001', name="Customers")
        group2 = TembaObjectRef.create(uuid='000-002', name="Spammers")

        # no differences (besides null field value which is ignored)
        first = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann", 'age': None}, language='eng', modified_on=timezone.now()
        )
        self.assertIsNone(temba_compare_contacts(first, second))
        self.assertIsNone(temba_compare_contacts(second, first))

        # different name
        second = TembaContact.create(
            uuid='000-001', name="Annie", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(temba_compare_contacts(first, second), 'name')

        # different URNs
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234', 'twitter:ann'], groups=[group1],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(temba_compare_contacts(first, second), 'urns')

        # different group
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group2],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(temba_compare_contacts(first, second), 'groups')
        self.assertEqual(temba_compare_contacts(first, second, groups=('000-001', '000-002')), 'groups')
        self.assertIsNone(temba_compare_contacts(first, second, groups=()))
        self.assertIsNone(temba_compare_contacts(first, second, groups=('000-003', '000-004')))

        # different field
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "annie"}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(temba_compare_contacts(first, second), 'fields')
        self.assertEqual(temba_compare_contacts(first, second, fields=('chat_name', 'gender')), 'fields')
        self.assertIsNone(temba_compare_contacts(first, second, fields=()))
        self.assertIsNone(temba_compare_contacts(first, second, fields=('age', 'gender')))

        # additional field
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann", 'age': 18}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(temba_compare_contacts(first, second), 'fields')
        self.assertIsNone(temba_compare_contacts(first, second, fields=()))
        self.assertIsNone(temba_compare_contacts(first, second, fields=('chat_name',)))

    def test_temba_merge_contacts(self):
        contact1 = TembaContact.create(
                uuid="000-001", name="Bob",
                urns=['tel:123', 'email:bob@bob.com'],
                fields={'chat_name': "bob", 'age': 23},
                groups=[
                    TembaObjectRef.create(uuid='000-001', name="Lusaka"),
                    TembaObjectRef.create(uuid='000-002', name="Seattle"),
                    TembaObjectRef.create(uuid='000-010', name="Customers")
                ]
        )
        contact2 = TembaContact.create(
                uuid="000-001", name="Bobby",
                urns=['tel:234', 'twitter:bob'],
                fields={'chat_name': "bobz", 'state': "IN"},
                groups=[
                    TembaObjectRef.create(uuid='000-003', name="Kigali"),
                    TembaObjectRef.create(uuid='000-009', name="Females"),
                    TembaObjectRef.create(uuid='000-011', name="Spammers")
                ]
        )

        merged = temba_merge_contacts(contact1, contact2, mutex_group_sets=(
            ('000-001', '000-002', '000-003'),  # Lusaka, Seattle, Kigali
            ('000-008', '000-009'),             # Males, Females
            ('000-098', '000-099'),             # other...
        ))
        self.assertEqual(merged.uuid, '000-001')
        self.assertEqual(merged.name, "Bob")
        self.assertEqual(sorted(merged.urns), ['email:bob@bob.com', 'tel:123', 'twitter:bob'])
        self.assertEqual(merged.fields, {'chat_name': "bob", 'age': 23, 'state': "IN"})

        merged_groups = sorted(merged.groups, key=lambda g: g.uuid)
        self.assertEqual([g.uuid for g in merged_groups], ['000-001', '000-009', '000-010', '000-011'])
        self.assertEqual([g.name for g in merged_groups], ["Lusaka", "Females", "Customers", "Spammers"])


@skip
class PerfTest(BaseCasesTest):

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
        self.assertEqual((num_fields, 0, 0), sync_pull_fields(self.unicef, Field))

        # setup get_groups
        groups = [TembaGroup.create(uuid="G0000000-0000-0000-0000-00000000%04d" % g, name="Group #%d" % g, count=0)
                  for g in range(0, num_groups)]
        mock_get_groups.return_value = MockClientQuery(groups)

        # sync groups
        self.assertEqual((num_groups, 0, 0), sync_pull_groups(self.unicef, Group))

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
                        TembaObjectRef.create(uuid="G0000000-0000-0000-0000-00000000%04d" % g, name="Group #%d" % g)
                        for g in range(0, groups_in)
                    ],
                    fields={'field_%d' % f: field_values[f % len(field_values)] for f in range(0, num_fields)},
                    failed=False,
                    blocked=False
                ))
            active_fetches.append(batch)

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]  # no deleted contacts

        start = time.time()
        num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact, inc_urns=False,
                                                                   prefetch_related=('groups', 'values__field'))

        print "Initial contact sync: %f secs" % (time.time() - start)

        self.assertEqual((num_created, num_updated, num_deleted), (num_fetches * fetch_size, 0, 0))

        # slowest_queries = sorted(connection.queries, key=lambda q: q['time'], reverse=True)[:10]

        # for q in slowest_queries:
        #    print "%s -- %s" % (q['time'], q['sql'])

        # simulate a subsequent sync with no changes
        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact, inc_urns=False,
                                                                   prefetch_related=('groups', 'values__field'))
        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

        print "Contact sync with no changes: %f secs" % (time.time() - start)

        # simulate an update of some fields
        for batch in active_fetches:
            for c in batch:
                c.fields['field_3'] = "ABCD"
                c.fields['field_5'] = "EFGH"
                c.fields['field_7'] = "IJKL"

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact, inc_urns=False,
                                                                   prefetch_related=('groups', 'values__field'))
        self.assertEqual((num_created, num_updated, num_deleted), (0, num_fetches * fetch_size, 0))

        print "Contact sync with field value changes: %f secs" % (time.time() - start)
