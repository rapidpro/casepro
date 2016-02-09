# coding=utf-8
from __future__ import unicode_literals

from casepro.test import BaseCasesTest
from temba_client.v2.types import Contact as TembaContact, ObjectRef as TembaObjectRef
from .models import Contact, Group


class ContactTest(BaseCasesTest):
    def test_save(self):
        kwargs = Contact.kwargs_from_temba(self.unicef, TembaContact.create(
                uuid="C-001",
                name="Bob McFlow",
                language="eng",
                urns=["twitter:bobflow"],
                groups=[TembaObjectRef.create(uuid="G-001", name="Customers")],
                fields={'age': "34"},
                failed=False,
                blocked=False
        ))

        self.assertEqual(kwargs, {
            'org': self.unicef,
            'uuid': "C-001",
            'name': "Bob McFlow",
            'language': "eng",
            '__data__groups': [("G-001", "Customers")],
            '__data__fields': {'age': "34"},
        })

        # check saving by result of kwargs_from_temba
        contact = Contact.objects.create(**kwargs)

        self.assertEqual(contact.uuid, "C-001")
        self.assertEqual(contact.name, "Bob McFlow")
        self.assertEqual(contact.language, "eng")
        self.assertEqual(contact.get_fields(), {"age": "34"})

        customers = Group.objects.get(org=self.unicef, uuid="G-001", name="Customers")

        self.assertEqual(set(contact.groups.all()), {customers})

        contact = Contact.objects.select_related('org').prefetch_related('groups', 'values__field').get(uuid='C-001')

        # check there are no extra db hits when saving without change, assuming appropriate pre-fetches (as above)
        with self.assertNumQueries(1):
            setattr(contact, '__data__groups', [("G-001", "Customers")])
            setattr(contact, '__data__fields', {"age": "34"})
            contact.save()

        # check removing a group and adding new ones
        with self.assertNumQueries(7):
            setattr(contact, '__data__groups', [("G-002", "Spammers"), ("G-003", "Boffins")])
            contact.save()

        # check updating a field
        with self.assertNumQueries(2):
            setattr(contact, '__data__fields', {"age": "35"})
            contact.save()

        # check adding a new field
        with self.assertNumQueries(4):
            setattr(contact, '__data__fields', {"age": "35", "state": "WA"})
            contact.save()

        # check deleting a field
        with self.assertNumQueries(4):
            setattr(contact, '__data__fields', {"state": "WA"})
            contact.save()

        contact = Contact.objects.get(uuid='C-001')

        self.assertEqual(contact.get_fields(), {"state": "WA"})

        spammers = Group.objects.get(org=self.unicef, uuid="G-002", name="Spammers")
        boffins = Group.objects.get(org=self.unicef, uuid="G-003", name="Boffins")

        self.assertEqual(set(contact.groups.all()), {spammers, boffins})
