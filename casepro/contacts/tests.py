# coding=utf-8
from __future__ import unicode_literals

from dash.orgs.models import TaskState
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from mock import patch

from casepro.test import BaseCasesTest

from .models import Contact, Group, Field
from .tasks import pull_contacts


class ContactTest(BaseCasesTest):
    def setUp(self):
        super(ContactTest, self).setUp()

        self.ann = self.create_contact(self.unicef, '7b7dd838-4947-4e85-9b5c-0e8b1794080b', "Ann", [self.reporters],
                                       {'age': "32", 'state': "WA"})

    def test_save(self):
        # start with no data
        Contact.objects.all().delete()
        Group.objects.all().delete()
        Field.objects.all().delete()

        contact = Contact.objects.create(
            org=self.unicef,
            uuid="C-001",
            name="Bob McFlow",
            language="eng",
            is_stub=False,
            fields={'age': "34"},
            __data__groups=[("G-001", "Customers")],
            urns=["tel:0821234567"],
        )

        self.assertEqual(contact.uuid, "C-001")
        self.assertEqual(contact.name, "Bob McFlow")
        self.assertEqual(contact.language, "eng")
        self.assertEqual(contact.get_fields(), {"age": "34"})
        self.assertEqual(contact.urns, ["tel:0821234567"])

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

    def test_get_display_name(self):
        self.assertEqual(self.ann.get_display_name(), "Ann")

        # if site uses anon contacts then obscure this
        with override_settings(SITE_ANON_CONTACTS=True):
            self.assertEqual(self.ann.get_display_name(), "7B7DD8")

        # likewise if name if empty
        self.ann.name = ""
        self.assertEqual(self.ann.get_display_name(), "7B7DD8")

    def test_get_fields(self):
        self.assertEqual(self.ann.get_fields(), {'age': "32", 'state': "WA"})  # what is stored on the contact
        self.assertEqual(self.ann.get_fields(visible=True), {'nickname': None, 'age': "32"})  # visible fields

    def test_release(self):
        self.create_message(self.unicef, 101, self.ann, "Hello")
        self.create_message(self.unicef, 102, self.ann, "Goodbye")

        self.ann.release()

        self.assertEqual(self.ann.groups.count(), 0)  # should be removed from groups
        self.assertEqual(self.ann.incoming_messages.count(), 2)  # messages should be inactive and handled
        self.assertEqual(self.ann.incoming_messages.filter(is_active=False, is_handled=True).count(), 2)

    def test_as_json(self):
        self.assertEqual(self.ann.as_json(full=False), {'id': self.ann.pk, 'name': "Ann"})

        # full=True means include visible contact fields and laanguage etc
        self.assertEqual(self.ann.as_json(full=True), {
            'id': self.ann.pk,
            'name': "Ann",
            'language': {'code': 'eng', 'name': "English"},
            'groups': [{'id': self.reporters.pk, 'name': "Reporters"}],
            'fields': {'nickname': None, 'age': "32"},
            'blocked': False,
            'stopped': False
        })

        self.ann.language = None
        self.ann.save()

        self.assertEqual(self.ann.as_json(full=True), {
            'id': self.ann.pk,
            'name': "Ann",
            'language': None,
            'groups': [{'id': self.reporters.pk, 'name': "Reporters"}],
            'fields': {'nickname': None, 'age': "32"},
            'blocked': False,
            'stopped': False
        })

        # if site uses anon contacts then name is obscured
        with override_settings(SITE_ANON_CONTACTS=True):
            self.assertEqual(self.ann.as_json(full=False), {'id': self.ann.pk, 'name': "7B7DD8"})

    @patch('casepro.test.TestBackend.push_contact')
    def test_get_or_create_from_urn_no_match(self, mock_push_contact):
        """
        If no contact with a matching urn exists a new one should be created
        """
        self.assertEqual(Contact.objects.count(), 1)
        Contact.get_or_create_from_urn(self.unicef, "tel:+27827654321")

        contacts = Contact.objects.all()
        self.assertEqual(len(contacts), 2)
        self.assertEqual(contacts[1].urns, ["tel:+27827654321"])
        self.assertIsNone(contacts[1].name)
        self.assertIsNone(contacts[1].uuid)

        # Check that the backend was updated
        self.assertTrue(mock_push_contact.called)

    @patch('casepro.test.TestBackend.push_contact')
    def test_get_or_create_from_urn_match(self, mock_push_contact):
        """
        Should return the contact with the matching urn
        """
        self.ann.urns = ["tel:+27827654321"]
        self.ann.save(update_fields=('urns',))

        self.assertEqual(Contact.objects.count(), 1)
        contact = Contact.get_or_create_from_urn(self.unicef, "tel:+27827654321")
        self.assertEqual(Contact.objects.count(), 1)

        self.assertEqual(contact.urns, ["tel:+27827654321"])
        self.assertEqual(contact.name, self.ann.name)
        self.assertEqual(contact.uuid, self.ann.uuid)

        # We shouldn't update the backend because a contact wasn't created
        self.assertFalse(mock_push_contact.called)

    @patch('casepro.test.TestBackend.push_contact')
    def test_get_or_create_from_urn_invalid(self, mock_push_contact):
        """
        Should raise an exception for InvalidURN
        """
        from casepro.utils import InvalidURN
        self.assertRaises(InvalidURN, Contact.get_or_create_from_urn, self.unicef, "tel:0827654321")


class ContactCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(ContactCRUDLTest, self).setUp()

        self.ann = self.create_contact(self.unicef, "C-001", "Ann", [self.reporters], {'age': "32"})

    def test_list(self):
        url = reverse('contacts.contact_list')

        # log in as a non-superuser
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 302)

        self.login(self.superuser)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['object_list']), [self.ann])

    def test_read(self):
        url = reverse('contacts.contact_read', args=[self.ann.pk])

        # log in as regular user
        self.login(self.user1)
        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "View External")

        # administrators get button linking to backend
        self.login(self.admin)
        response = self.url_get('unicef', url)
        self.assertContains(response, "View External")

        # users from other orgs get nothing
        self.login(self.user4)
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

    def test_fetch(self):
        url = reverse('contacts.contact_fetch', args=[self.ann.pk])

        # log in as regular user
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            'id': self.ann.pk,
            'name': "Ann",
            'language': {'code': 'eng', 'name': "English"},
            'fields': {'age': '32', 'nickname': None},
            'groups': [{'id': self.reporters.pk, 'name': "Reporters"}],
            'blocked': False,
            'stopped': False
        })

    def test_cases(self):
        url = reverse('contacts.contact_cases', args=[self.ann.pk])

        msg1 = self.create_message(self.unicef, 101, self.ann, "What is tea?")
        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1, [])
        case1.close(self.admin)
        msg2 = self.create_message(self.unicef, 102, self.ann, "I'm pregnant")
        case2 = self.create_case(self.unicef, self.ann, self.moh, msg2, [self.pregnancy, self.aids])

        # log in as admin
        self.login(self.admin)

        # should see all cases in reverse chronological order
        response = self.url_get('unicef', url)
        self.assertEqual([c['id'] for c in response.json['results']], [case2.pk, case1.pk])

        self.login(self.user1)

        # should see both cases because of assignment/labels
        response = self.url_get('unicef', url)
        self.assertEqual([c['id'] for c in response.json['results']], [case2.pk, case1.pk])

        self.login(self.user3)

        # should see only case with pregnancy label
        response = self.url_get('unicef', url)
        self.assertEqual([c['id'] for c in response.json['results']], [case2.pk])


class FieldCRUDLTest(BaseCasesTest):
    def test_list(self):
        url = reverse('contacts.field_list')

        # partner users can't access this
        self.login(self.user1)
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # org admins can
        self.login(self.admin)
        response = self.url_get('unicef', url)
        self.assertEqual(list(response.context['object_list']), [self.age, self.nickname, self.state])


class GroupTest(BaseCasesTest):
    def test_model(self):
        invisible = self.create_group(self.unicef, "G-006", "Invisible", count=12, is_visible=False)

        self.assertEqual(set(Group.get_all(self.unicef)),
                         {self.males, self.females, self.reporters, self.registered, invisible})

        self.assertEqual(set(Group.get_all(self.unicef, visible=True)),
                         {self.males, self.females, self.registered})

        self.assertEqual(set(Group.get_all(self.unicef, dynamic=False)),
                         {self.males, self.females, self.reporters, invisible})

        self.assertEqual(invisible.as_json(full=True), {
            'id': invisible.pk,
            'name': "Invisible",
            'count': 12,
            'is_dynamic': False
        })
        self.assertEqual(invisible.as_json(full=False), {'id': invisible.pk, 'name': "Invisible"})


class GroupCRUDLTest(BaseCasesTest):
    def test_list(self):
        url = reverse('contacts.group_list')

        # partner users can't access this
        self.login(self.user1)
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # org admins can
        self.login(self.admin)
        response = self.url_get('unicef', url)
        self.assertEqual(list(response.context['object_list']), [self.females, self.males, self.registered])

    def test_select(self):
        url = reverse('contacts.group_select')

        # partner users can't access this
        self.login(self.user1)
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # org admins can
        self.login(self.admin)
        response = self.url_get('unicef', url)
        self.assertEqual(set(response.context['form']['groups'].field.initial),
                         {self.females.pk, self.males.pk, self.registered.pk})

        # change the visible groups
        response = self.url_post('unicef', url, {'groups': [self.females.pk, self.reporters.pk]})
        self.assertRedirects(response, 'http://unicef.localhost/group/', fetch_redirect_response=False)

        self.assertEqual(set(Group.get_all(self.unicef, visible=True)), {self.females, self.reporters})
        self.assertEqual(set(Group.get_all(self.unicef, visible=False)), {self.males, self.registered})


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
