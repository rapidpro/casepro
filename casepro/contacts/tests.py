from dash.orgs.models import TaskState
from django.urls import reverse
from django.test.utils import override_settings
from unittest.mock import patch

from casepro.test import BaseCasesTest

from .models import URN, Contact, Field, Group, InvalidURN
from .tasks import pull_contacts


class URNTest(BaseCasesTest):
    def test_from_parts(self):
        self.assertEqual(URN.from_parts("tel", "12345"), "tel:12345")
        self.assertEqual(URN.from_parts("tel", "+12345"), "tel:+12345")
        self.assertEqual(URN.from_parts("tel", "(917) 992-5253"), "tel:(917) 992-5253")
        self.assertEqual(URN.from_parts("mailto", "a_b+c@d.com"), "mailto:a_b+c@d.com")

        self.assertRaises(ValueError, URN.from_parts, "", "12345")
        self.assertRaises(ValueError, URN.from_parts, "tel", "")
        self.assertRaises(ValueError, URN.from_parts, "xxx", "12345")

    def test_to_parts(self):
        self.assertEqual(URN.to_parts("tel:12345"), ("tel", "12345"))
        self.assertEqual(URN.to_parts("tel:+12345"), ("tel", "+12345"))
        self.assertEqual(URN.to_parts("twitter:abc_123"), ("twitter", "abc_123"))
        self.assertEqual(URN.to_parts("mailto:a_b+c@d.com"), ("mailto", "a_b+c@d.com"))

        self.assertRaises(ValueError, URN.to_parts, "tel")
        self.assertRaises(ValueError, URN.to_parts, "tel:")  # missing scheme
        self.assertRaises(ValueError, URN.to_parts, ":12345")  # missing path
        self.assertRaises(ValueError, URN.to_parts, "x_y:123")  # invalid scheme
        self.assertRaises(ValueError, URN.to_parts, "xyz:{abc}")  # invalid path

    def test_normalize(self):
        # valid tel numbers
        self.assertEqual(URN.normalize("tel: +250788383383 "), "tel:+250788383383")
        self.assertEqual(URN.normalize("tel:+1(917)992-5253"), "tel:+19179925253")
        self.assertEqual(URN.normalize("tel:250788383383"), "tel:+250788383383")

        # un-normalizable tel numbers
        self.assertEqual(URN.normalize("tel:12345"), "tel:12345")
        self.assertEqual(URN.normalize("tel:0788383383"), "tel:0788383383")
        self.assertEqual(URN.normalize("tel:MTN"), "tel:mtn")

        # twitter handles remove @
        self.assertEqual(URN.normalize("twitter: @jimmyJO"), "twitter:jimmyjo")

        # email addresses
        self.assertEqual(URN.normalize("mailto: nAme@domAIN.cOm "), "mailto:name@domain.com")

    def test_validate(self):
        self.assertTrue(URN.validate("tel:+27825552233"))
        self.assertRaises(InvalidURN, URN.validate, "tel:0825550011")
        self.assertTrue(URN.validate("unknown_scheme:address_for_unknown_scheme"))

    def test_validate_phone(self):
        self.assertRaises(InvalidURN, URN.validate_phone, "0825550011")  # lacks country code
        self.assertRaises(InvalidURN, URN.validate_phone, "(+27)825550011")  # incorrect format (E.123)
        self.assertRaises(InvalidURN, URN.validate_phone, "+278255500abc")  # incorrect format
        self.assertRaises(InvalidURN, URN.validate_phone, "+278255500115555555")  # too long
        self.assertTrue(URN.validate_phone("+27825552233"))


class ContactTest(BaseCasesTest):
    def setUp(self):
        super(ContactTest, self).setUp()

        self.ann = self.create_contact(
            self.unicef, "7b7dd838-4947-4e85-9b5c-0e8b1794080b", "Ann", [self.reporters], {"age": "32", "state": "WA"}
        )

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
            fields={"age": "34"},
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

        contact = Contact.objects.select_related("org").prefetch_related("groups").get(uuid="C-001")

        # check there are no extra db hits when saving without change, assuming appropriate pre-fetches (as above)
        with self.assertNumQueries(1):
            setattr(contact, "__data__groups", [("G-001", "Customers")])
            contact.save()

        # check removing a group and adding new ones
        with self.assertNumQueries(7):
            setattr(contact, "__data__groups", [("G-002", "Spammers"), ("G-003", "Boffins")])
            contact.save()

        contact = Contact.objects.get(uuid="C-001")

        spammers = Group.objects.get(org=self.unicef, uuid="G-002", name="Spammers")
        boffins = Group.objects.get(org=self.unicef, uuid="G-003", name="Boffins")

        self.assertEqual(set(contact.groups.all()), {spammers, boffins})

    def test_get_display(self):
        # if the site uses 'uuid' for the display
        with override_settings(SITE_CONTACT_DISPLAY="uuid"):
            self.assertEqual(self.ann.get_display(), "7B7DD8")

        # if the site uses 'urns' for the display
        self.ann.urns = ["tel:+2345"]
        with override_settings(SITE_CONTACT_DISPLAY="urns"):
            self.assertEqual(self.ann.get_display(), "+2345")
        self.ann.refresh_from_db()

        # if the site uses 'name' or something unrecognised for the display
        self.assertEqual(self.ann.get_display(), "Ann")
        self.ann.name = None
        self.assertEqual(self.ann.get_display(), "---")

    def test_get_fields(self):
        self.assertEqual(self.ann.get_fields(), {"age": "32", "state": "WA"})  # what is stored on the contact
        self.assertEqual(self.ann.get_fields(visible=True), {"nickname": None, "age": "32"})  # visible fields

    def test_release(self):
        self.create_message(self.unicef, 101, self.ann, "Hello")
        self.create_message(self.unicef, 102, self.ann, "Goodbye")

        self.ann.release()

        self.assertEqual(self.ann.groups.count(), 0)  # should be removed from groups
        self.assertEqual(self.ann.incoming_messages.count(), 2)  # messages should be inactive and handled
        self.assertEqual(self.ann.incoming_messages.filter(is_active=False, is_handled=True).count(), 2)

    def test_as_json(self):
        self.assertEqual(self.ann.as_json(full=False), {"id": self.ann.pk, "display": "Ann"})

        # full=True means include visible contact fields and laanguage etc
        self.assertEqual(
            self.ann.as_json(full=True),
            {
                "id": self.ann.pk,
                "display": "Ann",
                "name": "Ann",
                "urns": [],
                "language": {"code": "eng", "name": "English"},
                "groups": [{"id": self.reporters.pk, "name": "Reporters"}],
                "fields": {"nickname": None, "age": "32"},
                "blocked": False,
                "stopped": False,
            },
        )

        self.ann.language = None
        self.ann.urns = ["tel:+2345678", "mailto:ann@test.com"]
        self.ann.save()

        self.assertEqual(
            self.ann.as_json(full=True),
            {
                "id": self.ann.pk,
                "display": "Ann",
                "name": "Ann",
                "urns": ["tel:+2345678", "mailto:ann@test.com"],
                "language": None,
                "groups": [{"id": self.reporters.pk, "name": "Reporters"}],
                "fields": {"nickname": None, "age": "32"},
                "blocked": False,
                "stopped": False,
            },
        )

        # If the urns and name fields are hidden they should not be returned
        # SITE_CONTACT_DISPLAY overrules this for the 'display' attr
        with override_settings(SITE_HIDE_CONTACT_FIELDS=["urns", "name"], SITE_CONTACT_DISPLAY="uuid"):
            self.assertEqual(
                self.ann.as_json(full=True),
                {
                    "id": self.ann.pk,
                    "display": "7B7DD8",
                    "urns": [],
                    "name": None,
                    "language": None,
                    "groups": [{"id": self.reporters.pk, "name": "Reporters"}],
                    "fields": {"nickname": None, "age": "32"},
                    "blocked": False,
                    "stopped": False,
                },
            )

    @patch("casepro.test.TestBackend.push_contact")
    def test_get_or_create_from_urn(self, mock_push_contact):
        """
        If no contact with a matching urn exists a new one should be created
        """
        Contact.objects.all().delete()

        # try with a URN that doesn't match an existing contact
        contact1 = Contact.get_or_create_from_urn(self.unicef, "tel:+27827654321")

        self.assertEqual(contact1.urns, ["tel:+27827654321"])
        self.assertIsNone(contact1.name)
        self.assertIsNone(contact1.uuid)

        # check that the backend was updated
        self.assertTrue(mock_push_contact.called)
        mock_push_contact.reset_mock()

        # try with a URN that does match an existing contact
        contact2 = Contact.get_or_create_from_urn(self.unicef, "tel:+27827654321")
        self.assertEqual(contact2, contact1)

        # we shouldn't update the backend because a contact wasn't created
        self.assertFalse(mock_push_contact.called)

        # URN will be normalized
        contact3 = Contact.get_or_create_from_urn(self.unicef, "tel:+(278)-2765-4321")
        self.assertEqual(contact3, contact1)

        # we shouldn't update the backend because a contact wasn't created
        self.assertFalse(mock_push_contact.called)

        # we get an exception if URN isn't valid (e.g. local number)
        self.assertRaises(InvalidURN, Contact.get_or_create_from_urn, self.unicef, "tel:0827654321")


class ContactCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(ContactCRUDLTest, self).setUp()

        self.ann = self.create_contact(self.unicef, "C-001", "Ann", [self.reporters], {"age": "32"})

    def test_list(self):
        url = reverse("contacts.contact_list")

        # log in as a non-superuser
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 302)

        self.login(self.superuser)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["object_list"]), [self.ann])

    def test_read(self):
        url = reverse("contacts.contact_read", args=[self.ann.pk])

        # log in as regular user
        self.login(self.user1)
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "View External")

        # administrators get button linking to backend
        self.login(self.admin)
        response = self.url_get("unicef", url)
        self.assertContains(response, "View External")

        # users from other orgs get nothing
        self.login(self.user4)
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

    def test_fetch(self):
        url = reverse("contacts.contact_fetch", args=[self.ann.pk])

        # log in as regular user
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "id": self.ann.pk,
                "display": "Ann",
                "name": "Ann",
                "urns": [],
                "language": {"code": "eng", "name": "English"},
                "fields": {"age": "32", "nickname": None},
                "groups": [{"id": self.reporters.pk, "name": "Reporters"}],
                "blocked": False,
                "stopped": False,
            },
        )

    def test_cases(self):
        url = reverse("contacts.contact_cases", args=[self.ann.pk])

        msg1 = self.create_message(self.unicef, 101, self.ann, "What is tea?")
        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1, [])
        case1.close(self.admin)
        msg2 = self.create_message(self.unicef, 102, self.ann, "I'm pregnant")
        case2 = self.create_case(self.unicef, self.ann, self.moh, msg2, [self.pregnancy, self.aids])

        # log in as admin
        self.login(self.admin)

        # should see all cases in reverse chronological order
        response = self.url_get("unicef", url)
        self.assertEqual([c["id"] for c in response.json["results"]], [case2.pk, case1.pk])

        self.login(self.user1)

        # should see both cases because of assignment/labels
        response = self.url_get("unicef", url)
        self.assertEqual([c["id"] for c in response.json["results"]], [case2.pk, case1.pk])

        self.login(self.user3)

        # should see only case with pregnancy label
        response = self.url_get("unicef", url)
        self.assertEqual([c["id"] for c in response.json["results"]], [case2.pk])


class FieldCRUDLTest(BaseCasesTest):
    def test_list(self):
        url = reverse("contacts.field_list")

        # partner users can't access this
        self.login(self.user1)
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # org admins can
        self.login(self.admin)
        response = self.url_get("unicef", url)
        self.assertEqual(list(response.context["object_list"]), [self.age, self.nickname, self.state])


class GroupTest(BaseCasesTest):
    def test_model(self):
        invisible = self.create_group(self.unicef, "G-006", "Invisible", count=12, is_visible=False)

        self.assertEqual(
            set(Group.get_all(self.unicef)), {self.males, self.females, self.reporters, self.registered, invisible}
        )

        self.assertEqual(set(Group.get_all(self.unicef, visible=True)), {self.males, self.females, self.registered})

        self.assertEqual(
            set(Group.get_all(self.unicef, dynamic=False)), {self.males, self.females, self.reporters, invisible}
        )

        self.assertEqual(
            invisible.as_json(full=True), {"id": invisible.pk, "name": "Invisible", "count": 12, "is_dynamic": False}
        )
        self.assertEqual(invisible.as_json(full=False), {"id": invisible.pk, "name": "Invisible"})


class GroupCRUDLTest(BaseCasesTest):
    def test_list(self):
        url = reverse("contacts.group_list")

        # partner users can't access this
        self.login(self.user1)
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # org admins can
        self.login(self.admin)
        response = self.url_get("unicef", url)
        self.assertEqual(list(response.context["object_list"]), [self.females, self.males, self.registered])

    def test_select(self):
        url = reverse("contacts.group_select")

        # partner users can't access this
        self.login(self.user1)
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # org admins can
        self.login(self.admin)
        response = self.url_get("unicef", url)
        self.assertEqual(
            set(response.context["form"]["groups"].field.initial), {self.females.pk, self.males.pk, self.registered.pk}
        )

        # change the visible groups
        response = self.url_post("unicef", url, {"groups": [self.females.pk, self.reporters.pk]})
        self.assertRedirects(response, "/group/", fetch_redirect_response=False)

        self.assertEqual(set(Group.get_all(self.unicef, visible=True)), {self.females, self.reporters})
        self.assertEqual(set(Group.get_all(self.unicef, visible=False)), {self.males, self.registered})


class TasksTest(BaseCasesTest):
    @patch("casepro.test.TestBackend.pull_fields")
    @patch("casepro.test.TestBackend.pull_groups")
    @patch("casepro.test.TestBackend.pull_contacts")
    def test_pull_contacts(self, mock_pull_contacts, mock_pull_groups, mock_pull_fields):
        mock_pull_fields.return_value = (1, 2, 3, 4)
        mock_pull_groups.return_value = (5, 6, 7, 8)
        mock_pull_contacts.return_value = (9, 10, 11, 12)

        pull_contacts(self.unicef.pk)

        task_state = TaskState.objects.get(org=self.unicef, task_key="contact-pull")
        self.assertEqual(
            task_state.get_last_results(),
            {
                "fields": {"created": 1, "updated": 2, "deleted": 3},
                "groups": {"created": 5, "updated": 6, "deleted": 7},
                "contacts": {"created": 9, "updated": 10, "deleted": 11},
            },
        )
