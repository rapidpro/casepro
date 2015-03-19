from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from mock import patch
from temba.types import Label as TembaLabel
from upartners.labels.models import Label
from upartners.test import UPartnersTest


class LabelTest(UPartnersTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND='memory')
    @patch('dash.orgs.models.TembaClient.get_labels')
    @patch('dash.orgs.models.TembaClient.create_label')
    def test_create(self, mock_create_label, mock_get_labels):
        mock_get_labels.return_value = [
            TembaLabel.create(uuid='L-101', name="Not Ebola", parent=None, count=12),
            TembaLabel.create(uuid='L-102', name="EBOLA", parent=None, count=123)
        ]
        mock_create_label.return_value = TembaLabel.create(uuid='L-103', name="Chat", parent=None, count=0)

        ebola = Label.create(self.unicef, "Ebola", "Msgs about ebola", ['ebola', 'fever'], [self.moh, self.who])
        self.assertEqual(ebola.org, self.unicef)
        self.assertEqual(ebola.name, "Ebola")
        self.assertEqual(ebola.description, "Msgs about ebola")
        self.assertEqual(ebola.keywords, 'ebola,fever')
        self.assertEqual(ebola.get_keywords(), ['ebola', 'fever'])
        self.assertEqual(set(ebola.get_partners()), {self.moh, self.who})
        self.assertEqual(unicode(ebola), "Ebola")

        # check that task fetched the UUID of the matching label in RapidPro
        mock_get_labels.assert_called_with(name="Ebola")
        self.assertEqual(Label.objects.get(pk=ebola.pk).uuid, 'L-102')

        # create local label with no match in RapidPro
        chat = Label.create(self.unicef, "Chat", "Chatting", ['chat'], [self.moh, self.who])
        self.assertEqual(Label.objects.get(pk=chat.pk).uuid, 'L-103')


class LabelCRUDLTest(UPartnersTest):
    def test_create(self):
        url = reverse('labels.label_create')

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # submit with no data
        response = self.url_post('unicef', url, dict())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'description', 'This field is required.')
        self.assertFormError(response, 'form', 'partners', 'This field is required.')

        # submit again with data
        response = self.url_post('unicef', url, dict(name="Ebola", description="Msgs about ebola",
                                                     keywords="ebola,fever", partners=[self.moh.pk, self.who.pk]))
        self.assertEqual(response.status_code, 302)

        ebola = Label.objects.get(name="Ebola")
        self.assertEqual(ebola.org, self.unicef)
        self.assertEqual(ebola.name, "Ebola")
        self.assertEqual(ebola.description, "Msgs about ebola")
        self.assertEqual(ebola.keywords, 'ebola,fever')
        self.assertEqual(ebola.get_keywords(), ['ebola', 'fever'])
        self.assertEqual(set(ebola.get_partners()), {self.moh, self.who})

    def test_list(self):
        url = reverse('labels.label_list')

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['object_list']), [self.aids, self.pregnancy])
