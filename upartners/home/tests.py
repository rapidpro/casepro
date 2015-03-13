from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse
from upartners.test import UPartnersTest


class HomeViewTest(UPartnersTest):
    def test_home(self):
        # can't access it anonymously
        response = self.url_get('unicef', reverse('home.home'))
        self.assertLoginRedirect(response, 'unicef', '/')

        # login as superuser
        self.login(self.superuser)

        response = self.url_get('unicef', reverse('home.home'))
        self.assertEqual(response.status_code, 200)

        # login as administrator
        self.login(self.admin)

        response = self.url_get('unicef', reverse('home.home'))
        self.assertEqual(response.status_code, 200)

        # login as regular user
        self.login(self.user1)

        response = self.url_get('unicef', reverse('home.home'))
        self.assertEqual(response.status_code, 200)
