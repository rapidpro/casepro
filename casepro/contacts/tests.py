# coding=utf-8
from __future__ import unicode_literals

import itertools
import six

from mock import patch
from casepro.test import BaseCasesTest
from temba_client.v2.types import Contact as TembaContact, ObjectRef as TembaObjectRef
from .models import Contact, Group
from .sync import sync_pull_contacts


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


class ContactTest(BaseCasesTest):
    def test_save(self):
        # check saving by result of kwargs_from_temba
        kwargs = Contact.kwargs_from_temba(self.unicef, TembaContact.create(
                uuid="C-001",
                name="Bob McFlow",
                language="eng",
                urns=["twitter:bobflow"],
                groups=[TembaObjectRef.create(uuid="G-001", name="Customers")],
                fields={'age': 34},
                failed=False,
                blocked=False
        ))

        self.assertEqual(kwargs, {
            'org': self.unicef,
            'uuid': "C-001",
            'name': "Bob McFlow",
            'fields': {"age": "34"},
            'language': "eng",
            '__data__groups': [("G-001", "Customers")]
        })

        contact = Contact.objects.create(**kwargs)

        self.assertEqual(contact.uuid, "C-001")
        self.assertEqual(contact.name, "Bob McFlow")
        self.assertEqual(contact.language, "eng")
        self.assertEqual(contact.fields, {"age": "34"})

        customers = Group.objects.get(org=self.unicef, uuid="G-001", name="Customers")

        self.assertEqual(set(contact.groups.all()), {customers})

        # check removing a group and adding new ones
        setattr(contact, '__data__groups', [("G-002", "Spammers"), ("G-003", "Boffins")])
        contact.save()

        spammers = Group.objects.get(org=self.unicef, uuid="G-002", name="Spammers")
        boffins = Group.objects.get(org=self.unicef, uuid="G-003", name="Boffins")

        self.assertEqual(set(contact.groups.all()), {spammers, boffins})

    @patch('dash.orgs.models.TembaClient2.get_contacts')
    def test_sync_pull(self, mock_get_contacts):
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

        num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact)

        self.assertEqual(num_created, 3)
        self.assertEqual(num_updated, 0)
        self.assertEqual(num_deleted, 0)
        self.assertEqual(Contact.objects.count(), 3)
        self.assertEqual(Contact.objects.filter(is_active=True).count(), 3)

        # contact groups will have been created too
        customers = Group.objects.get(org=self.unicef, uuid="G-001", name="Customers", is_active=True)
        spammers = Group.objects.get(org=self.unicef, uuid="G-002", name="Spammers", is_active=True)

        bob = Contact.objects.get(uuid="C-001")
        self.assertEqual(bob.name, "Bob McFlow")
        self.assertEqual(bob.language, "eng")
        self.assertEqual(set(bob.groups.all()), {customers})
        self.assertEqual(bob.fields, {'age': "34"})

        mock_get_contacts.side_effect = [
            # first call to get active contacts will return two fetches of 2 and 1 contacts
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001", name="Bob McFlough", language="fre", urns=["twitter:bobflow"],
                        groups=[TembaObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={'age': 35}, failed=True, blocked=False
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

        num_created, num_updated, num_deleted = sync_pull_contacts(self.unicef, Contact)

        self.assertEqual(num_created, 0)
        self.assertEqual(num_updated, 1)
        self.assertEqual(num_deleted, 1)
        self.assertEqual(Contact.objects.count(), 3)
        self.assertEqual(Contact.objects.filter(is_active=True).count(), 2)

        bob.refresh_from_db()
        self.assertEqual(bob.name, "Bob McFlough")
        self.assertEqual(bob.language, "fre")
        self.assertEqual(set(bob.groups.all()), {spammers})
        self.assertEqual(bob.fields, {'age': "35"})
