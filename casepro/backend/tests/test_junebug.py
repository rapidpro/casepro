from casepro.contacts.models import Contact, Field, Group
from casepro.msgs.models import Label, Message
from casepro.test import BaseCasesTest

from ..junebug import JunebugBackend


class JunebugBackendTest(BaseCasesTest):
    def setUp(self):
        super(JunebugBackendTest, self).setUp()
        self.backend = JunebugBackend()

    def test_pull_contacts(self):
        '''
        Pulling all of the contacts should be a noop.
        '''
        Contact.objects.all().delete()

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, None, None)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Contact.objects.count(), 0)

    def test_pull_fields(self):
        '''
        Pulling all the fields should be a noop.
        '''
        Field.objects.all().delete()

        (created, updated, deleted, ignored) = self.backend.pull_fields(
            self.unicef)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Field.objects.count(), 0)

    def test_pull_groups(self):
        '''
        Pulling all groups should be a noop.
        '''
        Group.objects.all().delete()

        (created, updated, deleted, ignored) = self.backend.pull_groups(
            self.unicef)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Group.objects.count(), 0)

    def test_pull_labels(self):
        '''
        Pulling all labels should be a noop.
        '''
        Label.objects.all().delete()

        (created, updated, deleted, ignored) = self.backend.pull_labels(
            self.unicef)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Label.objects.count(), 0)

    def test_pull_messages(self):
        '''
        Pulling all messages should be a noop.
        '''
        Message.objects.all().delete()

        (created, updated, deleted, ignored) = self.backend.pull_messages(
            self.unicef, None, None)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Message.objects.count(), 0)

    def test_push_label(self):
        '''
        Pushing a new label should be a noop.
        '''
        old_tea = self.tea.__dict__.copy()
        self.backend.push_label(self.unicef, 'new label')
        self.tea.refresh_from_db()
        self.assertEqual(self.tea.__dict__, old_tea)

    def test_outgoing(self):
        '''
        Sending outgoing messages should send via Junebug.
        '''
        # TODO: Implement and test outgoing messages.

    def test_add_to_group(self):
        '''
        Adding a contact to a group should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        self.backend.add_to_group(self.unicef, bob, self.reporters)

        bob.refresh_from_db()
        self.assertEqual(bob.groups.count(), 0)

    def test_remove_from_group(self):
        '''
        Removing a contact from a group should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        bob.groups.add(self.reporters)
        self.backend.remove_from_group(self.unicef, bob, self.reporters)

        bob.refresh_from_db()
        self.assertEqual(bob.groups.count(), 1)

    def test_stop_runs(self):
        '''
        Stopping messages for a contact should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        old_bob = bob.__dict__.copy()
        self.backend.stop_runs(self.unicef, bob)

        bob.refresh_from_db()
        self.assertEqual(bob.__dict__, old_bob)

    def test_label_messages(self):
        '''
        Labelling messages should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_message(self.unicef, 123, bob, "Hello")
        self.backend.label_messages(self.unicef, [msg], self.aids)

        msg.refresh_from_db()
        self.assertEqual(msg.labels.count(), 0)

    def test_unlabel_messages(self):
        '''
        Unlabelling messages should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_message(self.unicef, 123, bob, "Hello")
        msg.labels.add(self.aids)
        self.backend.unlabel_messages(self.unicef, [msg], self.aids)

        msg.refresh_from_db()
        self.assertEqual(msg.labels.count(), 1)

    def test_archive_messages(self):
        '''
        Archiving messages should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_message(self.unicef, 123, bob, "Hello")
        self.backend.archive_messages(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertEqual(msg.is_archived, False)

    def test_archive_contact_messages(self):
        '''
        Archiving a contact's messages should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_message(self.unicef, 123, bob, "Hello")
        self.backend.archive_contact_messages(self.unicef, bob)

        msg.refresh_from_db()
        self.assertEqual(msg.is_archived, False)

    def test_restore_messages(self):
        '''
        Restoring messages should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_message(
            self.unicef, 123, bob, "Hello", is_archived=True)
        self.backend.restore_messages(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertEqual(msg.is_archived, True)

    def test_flag_messages(self):
        '''
        Flagging messages should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_message(self.unicef, 123, bob, "Hello")
        self.backend.flag_messages(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertEqual(msg.is_flagged, False)

    def test_unflag_messages(self):
        '''
        Unflagging messages should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_message(
            self.unicef, 123, bob, "Hello", is_flagged=True)
        self.backend.unflag_messages(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertEqual(msg.is_flagged, True)

    def test_fetch_contact_messages(self):
        '''
        Fetching a list of messages for a contact should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        messages = self.backend.fetch_contact_messages(
            self.unicef, bob, None, None)
        self.assertEqual(messages, [])

    def test_get_url_patterns(self):
        '''
        Should return the list of url patterns needed to receive messages
        from Junebug.
        '''
        # TODO: Implement the views needed for receiving messages.
