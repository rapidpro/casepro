from django.urls import reverse

from casepro.test import BaseCasesTest


class APITest(BaseCasesTest):

    def test_authentication(self):
        url = reverse("api.case-list")

        # test without authentication
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 403)

        # test with token authentication
        self.assertIsNotNone(self.admin.auth_token)

        response = self.url_get("unicef", url, HTTP_AUTHORIZATION="Token %s" % self.admin.auth_token.key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'count': 0, 'next': None, 'previous': None, 'results': []})

        # test with session authentication (with non-admin user)
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 403)

        # test with session authentication (with admin user)
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'count': 0, 'next': None, 'previous': None, 'results': []})
