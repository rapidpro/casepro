# coding=utf-8
from __future__ import unicode_literals

from casepro.test import BaseCasesTest
from dash.orgs.models import TaskState
from mock import patch
from .models import Contact, Group, Field
from .tasks import pull_contacts


class ContactTest(BaseCasesTest):
    def test_save(self):
        # start with no groups or fields
        Group.objects.all().delete()
        Field.objects.all().delete()

        contact = Contact.objects.create(
            org=self.unicef,
            uuid="C-001",
            name="Bob McFlow",
            language="eng",
            is_stub=False,
            fields={'age': "34"},
            __data__groups=[("G-001", "Customers")]
        )

        self.assertEqual(contact.uuid, "C-001")
        self.assertEqual(contact.name, "Bob McFlow")
        self.assertEqual(contact.language, "eng")
        self.assertEqual(contact.get_fields(), {"age": "34"})

        customers = Group.objects.get(org=self.unicef, uuid="G-001", name="Customers")

        self.assertEqual(set(contact.groups.all()), {customers})

        contact = Contact.objects.select_related('org').prefetch_related('groups').get(uuid='C-001')

        # check there are no extra db hits when saving without change, assuming appropriate pre-fetches (as above)
        with self.assertNumQueries(1):
            setattr(contact, '__data__groups', [("G-001", "Customers")])
            contact.save()

        # check removing a group and adding new ones
        with self.assertNumQueries(7):
            setattr(contact, '__data__groups', [("G-002", "Spammers"), ("G-003", "Boffins")])
            contact.save()

        contact = Contact.objects.get(uuid='C-001')

        spammers = Group.objects.get(org=self.unicef, uuid="G-002", name="Spammers")
        boffins = Group.objects.get(org=self.unicef, uuid="G-003", name="Boffins")

        self.assertEqual(set(contact.groups.all()), {spammers, boffins})

    def test_get_fields(self):
        contact = self.create_contact(self.unicef, 'C-001', "Jean", fields={'age': "32", 'state': "WA"})

        self.assertEqual(contact.get_fields(), {'age': "32", 'state': "WA"})  # what is stored on the contact
        self.assertEqual(contact.get_fields(visible=True), {'nickname': None, 'age': "32"})  # visible fields

    def test_release(self):
        contact = self.create_contact(self.unicef, 'C-001', "Jean", [self.reporters], {'age': "32"})
        self.create_message(self.unicef, 101, contact, "Hello")
        self.create_message(self.unicef, 102, contact, "Goodbye")

        contact.release()

        self.assertEqual(contact.groups.count(), 0)  # should be removed from groups
        self.assertEqual(contact.incoming_messages.count(), 2)  # messages should be inactive and handled
        self.assertEqual(contact.incoming_messages.filter(is_active=False, is_handled=True).count(), 2)

    def test_as_json(self):
        contact = self.create_contact(self.unicef, 'C-001', "Richard", fields={'age': "32", 'state': "WA"})

        self.assertEqual(contact.as_json(full=False), {'uuid': 'C-001', 'is_stub': False})

        # full=True means include visible contact fields
        self.assertEqual(contact.as_json(full=True), {'uuid': 'C-001',
                                                      'is_stub': False,
                                                      'fields': {'nickname': None, 'age': "32"}})


class TasksTest(BaseCasesTest):
    @patch('casepro.test.TestBackend.pull_fields')
    @patch('casepro.test.TestBackend.pull_groups')
    @patch('casepro.test.TestBackend.pull_contacts')
    def test_pull_contacts(self, mock_pull_contacts, mock_pull_groups, mock_pull_fields):
        mock_pull_fields.return_value = (1, 2, 3, 4)
        mock_pull_groups.return_value = (5, 6, 7, 8)
        mock_pull_contacts.return_value = (9, 10, 11, 12)

        pull_contacts(self.unicef.pk)

        task_state = TaskState.objects.get(org=self.unicef, task_key='contact-pull')
        self.assertEqual(task_state.get_last_results(), {
            'fields': {'created': 1, 'updated': 2, 'deleted': 3},
            'groups': {'created': 5, 'updated': 6, 'deleted': 7},
            'contacts': {'created': 9, 'updated': 10, 'deleted': 11}
        })
