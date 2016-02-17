# coding=utf-8
from __future__ import unicode_literals

from casepro.test import BaseCasesTest
from mock import patch
from temba_client.v1.types import Message as TembaMessage1
from .rapidpro import RapidProBackend


class RapidProBackendTest(BaseCasesTest):

    def setUp(self):
        super(RapidProBackendTest, self).setUp()

        self.backend = RapidProBackend()

    @patch('dash.orgs.models.TembaClient1.get_messages')
    @patch('dash.orgs.models.TembaClient1.archive_messages')
    def test_archive_contact_messages(self, mock_archive_messages, mock_get_messages):
        mock_get_messages.return_value = [TembaMessage1.create(id=123), TembaMessage1.create(id=234)]

        bob = self.create_contact(self.unicef, 'C-001', "Bob")

        self.backend.archive_contact_messages(self.unicef, bob)

        mock_get_messages.assert_called_once_with(contacts=['C-001'], direction='I', statuses=['H'], _types=['I'], archived=False)
        mock_archive_messages.assert_called_once_with(messages=[123, 234])
