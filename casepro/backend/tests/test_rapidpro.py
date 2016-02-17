# coding=utf-8
from __future__ import unicode_literals

from casepro.msgs.models import Message
from casepro.test import BaseCasesTest
from django.utils.timezone import now
from mock import patch
from temba_client.v1.types import Message as TembaMessage1
from ..rapidpro import RapidProBackend


class RapidProBackendTest(BaseCasesTest):

    def setUp(self):
        super(RapidProBackendTest, self).setUp()

        self.backend = RapidProBackend()
        self.bob = self.create_contact(self.unicef, 'C-001', "Bob")

    @patch('dash.orgs.models.TembaClient1.expire_contacts')
    def test_stop_runs(self, mock_expire_contacts):
        self.backend.stop_runs(self.unicef, self.bob)

        mock_expire_contacts.assert_called_once_with(['C-001'])

    @patch('dash.orgs.models.TembaClient1.archive_messages')
    def test_archive_messages(self, mock_archive_messages):
        # empty message list shouldn't make API call
        self.backend.archive_messages(self.unicef, [])

        mock_archive_messages.assert_not_called()

        msg1 = Message.objects.create(org=self.unicef, backend_id=123, contact=self.bob, text="Hello", type="I", created_on=now())
        msg2 = Message.objects.create(org=self.unicef, backend_id=234, contact=self.bob, text="Goodbye", type="I", created_on=now())

        self.backend.archive_messages(self.unicef, [msg1, msg2])

        mock_archive_messages.assert_called_once_with(messages=[123, 234])

    @patch('dash.orgs.models.TembaClient1.get_messages')
    @patch('dash.orgs.models.TembaClient1.archive_messages')
    def test_archive_contact_messages(self, mock_archive_messages, mock_get_messages):
        mock_get_messages.return_value = [TembaMessage1.create(id=123), TembaMessage1.create(id=234)]

        self.backend.archive_contact_messages(self.unicef, self.bob)

        mock_get_messages.assert_called_once_with(contacts=['C-001'], direction='I', statuses=['H'], _types=['I'], archived=False)
        mock_archive_messages.assert_called_once_with(messages=[123, 234])
