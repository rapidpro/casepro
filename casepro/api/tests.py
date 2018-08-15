import pytz

from django.urls import reverse

from casepro.test import BaseCasesTest


class APITest(BaseCasesTest):
    def setUp(self):
        super(APITest, self).setUp()

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

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"],
            [
                {
                    "id": case2.id,
                    "labels": [],
                    "assignee": {"id": self.who.id, "name": "WHO"},
                    "contact": {"uuid": str(case2.contact.uuid)},
                    "opened_on": self._format_date(case2.opened_on),
                    "closed_on": None,
                    "summary": "Summary 2",
                },
                {
                    "id": case1.id,
                    "labels": [{"uuid": "L-001", "name": "AIDS"}],
                    "assignee": {"id": self.moh.id, "name": "MOH"},
                    "contact": {"uuid": str(case1.contact.uuid)},
                    "opened_on": self._format_date(case1.opened_on),
                    "closed_on": None,
                    "summary": "Summary 1",
                },
            ],
        )

    def _format_date(self, d):
        """
        Helper function which formats a date exactly how DRF's DateTimeField does it
        """
        s = d.isoformat()
        if s.endswith("+00:00"):
            s = s[:-6] + "Z"
        return s
