# coding=utf-8
from __future__ import unicode_literals

import itertools
import six

from casepro.contacts.models import Contact, Group, Field
from casepro.test import BaseCasesTest
from django.utils import timezone
from mock import patch
from temba_client.v2.types import Group as TembaGroup, Field as TembaField
from temba_client.v2.types import Contact as TembaContact, ObjectRef as TembaObjectRef
from .sync import sync_pull_groups, sync_pull_fields, sync_pull_contacts, temba_compare_contacts, temba_merge_contacts


class MockClientQuery(six.Iterator):
    """
    Mock for APIv2 client get method return values (TODO move to Dash)
    """
    def __init__(self, *fetches):
        self.fetches = list(fetches)

    def iterfetches(self, retry_on_rate_exceed=False):
        return self

    def all(self, retry_on_rate_exceed=False):
        return list(itertools.chain.from_iterable(self.fetches))

    def first(self, retry_on_rate_exceed=False):
        return self.fetches[0][0] if self.fetches[0] else None

    def __iter__(self):
        return self

    def __next__(self):
        if not self.fetches:
            raise StopIteration()

        return self.fetches.pop(0)


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

    @patch('dash.orgs.models.TembaClient2.get_fields')
    def test_sync_pull_fields(self, mock_get_fields):
        # start with no fields
        Field.objects.all().delete()

        mock_get_fields.return_value = MockClientQuery([
            TembaField.create(key="nick_name", label="Nickname", value_type="text"),
            TembaField.create(key="age", label="Age", value_type="decimal"),
        ])

        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted = sync_pull_fields(self.unicef, Field)

        self.assertEqual((num_created, num_updated, num_deleted), (2, 0, 0))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=True)
        Field.objects.get(key="age", label="Age", value_type="N", is_active=True)

        mock_get_fields.return_value = MockClientQuery([
            TembaField.create(key="age", label="Age (Years)", value_type="decimal"),
            TembaField.create(key="homestate", label="Homestate", value_type="state"),
        ])

        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted = sync_pull_fields(self.unicef, Field)

        self.assertEqual((num_created, num_updated, num_deleted), (1, 1, 1))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=False)
        Field.objects.get(key="age", label="Age (Years)", value_type="N", is_active=True)
        Field.objects.get(key="homestate", label="Homestate", value_type="S", is_active=True)

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
                        fields={'age': 34}, failed=False, blocked=False
                    ),
                    TembaContact.create(
                        uuid="C-002", name="Jim McMsg", language="fre", urns=["tel:+250783835665"],
                        groups=[TembaObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={'age': 67}, failed=False, blocked=False
                    ),
                ],
                [
                    TembaContact.create(
                        uuid="C-003", name="Ann McPoll", language="eng", urns=["tel:+250783835664"],
                        groups=[],
                        fields={'age': 35}, failed=True, blocked=False
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

        with self.assertNumQueries(24):
            num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact, inc_urns=False,
                                                                       prefetch_related=('groups',))

        self.assertEqual((num_created, num_updated, num_deleted), (3, 0, 0))

        bob = Contact.objects.get(uuid="C-001")
        jim = Contact.objects.get(uuid="C-002")
        ann = Contact.objects.get(uuid="C-003")

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, jim, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), set())

        # contact groups will have been created too
        customers = Group.objects.get(org=self.unicef, uuid="G-001", name="Customers", is_active=True)
        spammers = Group.objects.get(org=self.unicef, uuid="G-002", name="Spammers", is_active=True)

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

        with self.assertNumQueries(13):
            num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact, inc_urns=False,
                                                                       prefetch_related=('groups',))

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
                                                                       prefetch_related=('groups',))
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

        with self.assertNumQueries(3):
            num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact,
                                                                       prefetch_related=('groups',))

        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 1))  # blocked = deleted for us

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), {bob, jim})

    def test_temba_compare_contacts(self):
        group1 = TembaObjectRef.create(uuid='000-001', name="Customers")
        group2 = TembaObjectRef.create(uuid='000-002', name="Spammers")

        # no differences
        first = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
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
