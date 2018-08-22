from django.utils.http import quote
from django.urls import reverse

from casepro.cases.models import CaseAction
from casepro.test import BaseCasesTest


class APITest(BaseCasesTest):
    def setUp(self):
        super().setUp()

        self.ann = self.create_contact(
            self.unicef, "C-001", "Ann", fields={"age": "34"}, groups=[self.females, self.reporters]
        )
        self.bob = self.create_contact(self.unicef, "C-002", "Bob")

    def test_authentication(self):
        url = reverse("api.case-list")

        # test without authentication
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 403)

        # test with token authentication
        self.assertIsNotNone(self.admin.auth_token)

        response = self.url_get("unicef", url, HTTP_AUTHORIZATION="Token %s" % self.admin.auth_token.key)
        self.assertEqual(response.status_code, 200)

        # test with session authentication (with non-admin user)
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 403)

        # test with session authentication (with admin user)
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

    def test_docs(self):
        response = self.url_get("unicef", reverse("api.root") + "?format=api")
        self.assertContains(response, "Login to see your access token", status_code=403)

        self.login(self.admin)

        response = self.url_get("unicef", reverse("api.root") + "?format=api")
        self.assertContains(response, self.admin.auth_token)

        response = self.url_get("unicef", reverse("api.case-list") + "?format=api")
        self.assertContains(response, self.admin.auth_token)

    def test_actions(self):
        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello", [self.aids])
        msg2 = self.create_message(self.unicef, 102, self.bob, "Bonjour")
        case1 = self.create_case(
            self.unicef, self.ann, self.moh, msg1, [self.aids], summary="Summary 1", user_assignee=self.user1
        )
        case2 = self.create_case(
            self.unicef, self.ann, self.who, msg2, [], summary="Summary 2", user_assignee=self.user1
        )

        case1.add_note(self.user1, "This is a note")
        case2.label(self.admin, self.pregnancy)
        case2.reassign(self.admin, self.moh)
        case2.close(self.admin)

        # case for another org
        msg3 = self.create_message(self.nyaruka, 103, self.bob, "Hola")
        case3 = self.create_case(
            self.nyaruka, self.ann, self.klab, msg3, [self.code], summary="Summary 3", user_assignee=self.user4
        )
        case3.add_note(self.user4, "Note!")

        url = reverse("api.action-list")
        self.login(self.admin)

        action1, action2, action3, action4 = CaseAction.objects.filter(org=self.unicef).order_by("id")

        # try listing all actions
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"],
            [
                {
                    "id": action4.id,
                    "case": {"id": case2.id, "summary": case2.summary},
                    "type": "close",
                    "assignee": None,
                    "note": None,
                    "label": None,
                    "created_on": self._format_date(action4.created_on),
                },
                {
                    "id": action3.id,
                    "case": {"id": case2.id, "summary": case2.summary},
                    "type": "reassign",
                    "assignee": {"id": self.moh.id, "name": "MOH"},
                    "note": None,
                    "label": None,
                    "created_on": self._format_date(action3.created_on),
                },
                {
                    "id": action2.id,
                    "case": {"id": case2.id, "summary": case2.summary},
                    "type": "label",
                    "assignee": None,
                    "note": None,
                    "label": {"id": self.pregnancy.id, "name": "Pregnancy"},
                    "created_on": self._format_date(action2.created_on),
                },
                {
                    "id": action1.id,
                    "case": {"id": case1.id, "summary": case1.summary},
                    "type": "add_note",
                    "assignee": None,
                    "note": "This is a note",
                    "label": None,
                    "created_on": self._format_date(action1.created_on),
                },
            ],
        )

        # try filtering by created_on
        response = self.url_get("unicef", url + f"?after={quote(action2.created_on.isoformat())}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([a["id"] for a in response.json()["results"]], [action4.id, action3.id])

        # try fetching a specific action from the detail endpoint
        url = reverse("api.action-detail", args=[action2.id])

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], action2.id)

    def test_cases(self):
        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello", [self.aids])
        msg2 = self.create_message(self.unicef, 102, self.bob, "Bonjour")
        case1 = self.create_case(
            self.unicef, self.ann, self.moh, msg1, [self.aids], summary="Summary 1", user_assignee=self.user1
        )
        case2 = self.create_case(
            self.unicef, self.ann, self.who, msg2, [], summary="Summary 2", user_assignee=self.user1
        )

        # case for another org
        msg3 = self.create_message(self.nyaruka, 103, self.bob, "Hola")
        self.create_case(
            self.nyaruka, self.ann, self.klab, msg3, [self.code], summary="Summary 3", user_assignee=self.user4
        )

        url = reverse("api.case-list")
        self.login(self.admin)

        # try listing all cases
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"],
            [
                {
                    "id": case2.id,
                    "summary": "Summary 2",
                    "labels": [],
                    "assignee": {"id": self.who.id, "name": "WHO"},
                    "contact": {"id": case1.contact.id, "uuid": str(case2.contact.uuid)},
                    "initial_message": {"id": msg2.id, "text": "Bonjour"},
                    "opened_on": self._format_date(case2.opened_on),
                    "closed_on": None,
                },
                {
                    "id": case1.id,
                    "summary": "Summary 1",
                    "labels": [{"id": self.aids.id, "name": "AIDS"}],
                    "assignee": {"id": self.moh.id, "name": "MOH"},
                    "contact": {"id": case1.contact.id, "uuid": str(case1.contact.uuid)},
                    "initial_message": {"id": msg1.id, "text": "Hello"},
                    "opened_on": self._format_date(case1.opened_on),
                    "closed_on": None,
                },
            ],
        )

        # try fetching a specific case from the detail endpoint
        url = reverse("api.case-detail", args=[case2.id])

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], case2.id)

    def test_labels(self):
        url = reverse("api.label-list")
        self.login(self.admin)

        # try listing all labels
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"],
            [
                {"id": self.tea.id, "name": "Tea", "description": "Messages about tea"},
                {"id": self.pregnancy.id, "name": "Pregnancy", "description": "Messages about pregnancy"},
                {"id": self.aids.id, "name": "AIDS", "description": "Messages about AIDS"},
            ],
        )

        # try fetching a specific label from the detail endpoint
        url = reverse("api.label-detail", args=[self.pregnancy.id])

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.pregnancy.id)

    def test_partners(self):
        url = reverse("api.partner-list")
        self.login(self.admin)

        # try listing all partners
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"],
            [
                {
                    "id": self.who.id,
                    "name": "WHO",
                    "description": "World Health Organisation",
                    "labels": [{"id": self.aids.id, "name": "AIDS"}],
                },
                {
                    "id": self.moh.id,
                    "name": "MOH",
                    "description": "Ministry of Health",
                    "labels": [{"id": self.aids.id, "name": "AIDS"}, {"id": self.pregnancy.id, "name": "Pregnancy"}],
                },
            ],
        )

        # try fetching a specific partner from the detail endpoint
        url = reverse("api.partner-detail", args=[self.who.id])

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.who.id)

    def _format_date(self, d):
        """
        Helper function which formats a date exactly how DRF's DateTimeField does it
        """
        s = d.isoformat()
        if s.endswith("+00:00"):
            s = s[:-6] + "Z"
        return s
