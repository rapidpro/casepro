# coding=utf-8
from __future__ import unicode_literals

from casepro.test import BaseCasesTest
from django.utils import timezone
from temba_client.v2.types import Contact as TembaContact, ObjectRef
from .sync import sync_compare_contacts, sync_merge_contacts


class SyncTest(BaseCasesTest):

    def test_sync_compare_contacts(self):
        group1 = ObjectRef.create(uuid='000-001', name="Customers")
        group2 = ObjectRef.create(uuid='000-002', name="Spammers")

        # no differences (besides null field value which is ignored)
        first = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann", 'age': None}, language='eng', modified_on=timezone.now()
        )
        self.assertIsNone(sync_compare_contacts(first, second))
        self.assertIsNone(sync_compare_contacts(second, first))

        # different name
        second = TembaContact.create(
            uuid='000-001', name="Annie", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(sync_compare_contacts(first, second), 'name')

        # different URNs
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234', 'twitter:ann'], groups=[group1],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(sync_compare_contacts(first, second), 'urns')

        # different group
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group2],
            fields={'chat_name': "ann"}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(sync_compare_contacts(first, second), 'groups')
        self.assertEqual(sync_compare_contacts(first, second, groups=('000-001', '000-002')), 'groups')
        self.assertIsNone(sync_compare_contacts(first, second, groups=()))
        self.assertIsNone(sync_compare_contacts(first, second, groups=('000-003', '000-004')))

        # different field
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "annie"}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(sync_compare_contacts(first, second), 'fields')
        self.assertEqual(sync_compare_contacts(first, second, fields=('chat_name', 'gender')), 'fields')
        self.assertIsNone(sync_compare_contacts(first, second, fields=()))
        self.assertIsNone(sync_compare_contacts(first, second, fields=('age', 'gender')))

        # additional field
        second = TembaContact.create(
            uuid='000-001', name="Ann", urns=['tel:1234'], groups=[group1],
            fields={'chat_name': "ann", 'age': 18}, language='eng', modified_on=timezone.now()
        )
        self.assertEqual(sync_compare_contacts(first, second), 'fields')
        self.assertIsNone(sync_compare_contacts(first, second, fields=()))
        self.assertIsNone(sync_compare_contacts(first, second, fields=('chat_name',)))

    def test_sync_merge_contacts(self):
        contact1 = TembaContact.create(
                uuid="000-001", name="Bob",
                urns=['tel:123', 'email:bob@bob.com'],
                fields={'chat_name': "bob", 'age': 23},
                groups=[
                    ObjectRef.create(uuid='000-001', name="Lusaka"),
                    ObjectRef.create(uuid='000-002', name="Seattle"),
                    ObjectRef.create(uuid='000-010', name="Customers")
                ]
        )
        contact2 = TembaContact.create(
                uuid="000-001", name="Bobby",
                urns=['tel:234', 'twitter:bob'],
                fields={'chat_name': "bobz", 'state': "IN"},
                groups=[
                    ObjectRef.create(uuid='000-003', name="Kigali"),
                    ObjectRef.create(uuid='000-009', name="Females"),
                    ObjectRef.create(uuid='000-011', name="Spammers")
                ]
        )

        merged = sync_merge_contacts(contact1, contact2, mutex_group_sets=(
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
