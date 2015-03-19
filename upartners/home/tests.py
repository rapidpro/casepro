from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from mock import patch
from temba.types import Label as TembaLabel
from upartners.test import UPartnersTest


class HomeViewTest(UPartnersTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND='memory')
    @patch('dash.orgs.models.TembaClient.get_labels')
    def test_home(self, mock_get_labels):
        mock_get_labels.return_value = [
            TembaLabel.create(uuid='L-001', name="AIDS", parent=None, count=1234),
            TembaLabel.create(uuid='L-002', name="Pregnancy", parent=None, count=2345)
        ]

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
        self.assertEqual(list(response.context['labels']), [self.aids, self.pregnancy])
        self.assertEqual(response.context['labels'][0].count, 1234)
        self.assertEqual(response.context['labels'][1].count, 2345)

        # login as partner user
        self.login(self.user1)

        response = self.url_get('unicef', reverse('home.home'))
        self.assertEqual(response.status_code, 200)
