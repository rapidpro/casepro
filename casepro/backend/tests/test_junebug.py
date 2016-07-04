from casepro.contacts.models import Contact, Field, Group
from casepro.msgs.models import Label, Message
from casepro.test import BaseCasesTest
from django.test import override_settings
import json
import responses

from ..junebug import IdentityStore, JunebugBackend, JunebugMessageSendingError


class JunebugBackendTest(BaseCasesTest):
    def setUp(self):
        super(JunebugBackendTest, self).setUp()
        self.backend = JunebugBackend()

    def add_identity_store_callback(self, query, callback):
        url = 'http://localhost:8081/api/v1/identities/search/?' + query
        responses.add_callback(
            responses.GET, url, callback=callback, match_querystring=True,
            content_type='application/json')

    def identity_store_no_matches_callback(self, request):
        headers = {'Content-Type': 'application/json'}
        resp = {
            "count": 0,
            "next": None,
            "previous": None,
            "results": []
        }
        return (201, headers, json.dumps(resp))

    def identity_store_created_identity_callback(self, request):
        headers = {'Content-Type': 'application/json'}
        resp = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": "test_id",
                    "version": 1,
                    "details": {
                        "name": "test",
                        "addresses": {
                            "msisdn": {
                                "+1234": {}
                            },
                        },
                        "preferred_langage": "eng_NG",
                    },
                    "communicate_through": None,
                    "operator": None,
                    "created_at": "2016-03-14T10:21:00.258406Z",
                    "created_by": 1,
                    "updated_at": None,
                    "updated_by": None
                }
            ]
        }
        return (201, headers, json.dumps(resp))

    def identity_store_updated_identity_callback(self, request):
        headers = {'Content-Type': 'application/json'}
        resp = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": "test_id",
                    "version": 1,
                    "details": {
                        "name": "test",
                        "addresses": {
                            "msisdn": {
                                "+1234": {}
                            },
                        },
                        "preferred_langage": "eng_NG",
                    },
                    "communicate_through": None,
                    "operator": None,
                    "created_at": "2016-02-14T10:21:00.258406Z",
                    "created_by": 1,
                    "updated_at": "2016-03-14T10:21:00.258406Z",
                    "updated_by": 1
                }
            ]
        }
        return (201, headers, json.dumps(resp))

    @responses.activate
    def test_pull_contacts_recently_created(self):
        Contact.objects.all().delete()

        self.add_identity_store_callback(
            'created_at__lte=2016-03-14T10%3A21%3A00&created_at__gte=2016-03-14T10%3A25%3A00',
            self.identity_store_created_identity_callback
        )

        self.add_identity_store_callback(
            'updated_at__lte=2016-03-14T10%3A21%3A00&updated_at__gte=2016-03-14T10%3A25%3A00',
            self.identity_store_no_matches_callback
        )

        self.add_identity_store_callback(
            'updated_at__lte=2016-03-14T10%3A21%3A00&updated_at__gte=2016-03-14T10%3A25%3A00&'
            'optout__optout_type=forget',
            self.identity_store_no_matches_callback
        )

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, '2016-03-14T10:25:00', '2016-03-14T10:21:00')
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Contact.objects.count(), 1)

    @responses.activate
    def test_pull_contacts_recently_updated(self):
        Contact.objects.all().delete()
        Contact.get_or_create(self.unicef, 'test_id', "test")

        self.add_identity_store_callback(
            'created_at__lte=2016-03-14T10%3A21%3A00&created_at__gte=2016-03-14T10%3A25%3A00',
            self.identity_store_no_matches_callback
        )

        self.add_identity_store_callback(
            'updated_at__lte=2016-03-14T10%3A21%3A00&updated_at__gte=2016-03-14T10%3A25%3A00',
            self.identity_store_updated_identity_callback
        )

        self.add_identity_store_callback(
            'updated_at__lte=2016-03-14T10%3A21%3A00&updated_at__gte=2016-03-14T10%3A25%3A00&'
            'optout__optout_type=forget',
            self.identity_store_no_matches_callback
        )

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, '2016-03-14T10:25:00', '2016-03-14T10:21:00')
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Contact.objects.count(), 1)

    @responses.activate
    def test_pull_contacts_recently_deleted(self):
        Contact.objects.all().delete()
        Contact.get_or_create(self.unicef, 'test_id', "test")

        self.add_identity_store_callback(
            'created_at__lte=2016-03-14T10%3A21%3A00&created_at__gte=2016-03-14T10%3A25%3A00',
            self.identity_store_no_matches_callback
        )

        self.add_identity_store_callback(
            'updated_at__lte=2016-03-14T10%3A21%3A00&updated_at__gte=2016-03-14T10%3A25%3A00',
            self.identity_store_no_matches_callback
        )

        self.add_identity_store_callback(
            'updated_at__lte=2016-03-14T10%3A21%3A00&updated_at__gte=2016-03-14T10%3A25%3A00&'
            'optout__optout_type=forget',
            self.identity_store_updated_identity_callback
        )

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, '2016-03-14T10:25:00', '2016-03-14T10:21:00')
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 1)
        self.assertEqual(ignored, 0)
        self.assertEqual(Contact.objects.count(), 1)

    @responses.activate
    def test_pull_contacts_no_changes(self):
        Contact.objects.all().delete()
        Contact.objects.create(org=self.unicef, uuid='test_id', name="test",
                               language='eng')

        self.add_identity_store_callback(
            'created_at__lte=2016-03-14T10%3A21%3A00&created_at__gte=2016-03-14T10%3A25%3A00',
            self.identity_store_no_matches_callback
        )

        self.add_identity_store_callback(
            'updated_at__lte=2016-03-14T10%3A21%3A00&updated_at__gte=2016-03-14T10%3A25%3A00',
            self.identity_store_updated_identity_callback
        )

        self.add_identity_store_callback(
            'updated_at__lte=2016-03-14T10%3A21%3A00&updated_at__gte=2016-03-14T10%3A25%3A00&'
            'optout__optout_type=forget',
            self.identity_store_no_matches_callback
        )

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, '2016-03-14T10:25:00', '2016-03-14T10:21:00')
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 1)
        self.assertEqual(Contact.objects.count(), 1)

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

    @responses.activate
    def test_outgoing_urn(self):
        '''
        Sending outgoing messages with a specified urn should send via Junebug
        with that URN.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_outgoing(
            self.unicef, self.user1, None, 'B', "That's great", bob,
            urn="tel:+1234")

        def request_callback(request):
            data = json.loads(request.body)
            self.assertEqual(data, {
                'to': '+1234', 'from': None, 'content': "That's great"})
            headers = {'Content-Type': 'application/json'}
            resp = {
                'status': 201,
                'code': 'created',
                'description': 'message submitted',
                'result': {
                    'id': 'message-uuid-1234',
                },
            }
            return (201, headers, json.dumps(resp))
        responses.add_callback(
            responses.POST,
            'http://localhost:8080/channels/replace-me/messages/',
            callback=request_callback, content_type='application/json')

        self.backend.push_outgoing(self.unicef, [msg])
        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_outgoing_contact(self):
        '''Sending outgoing message with a specified contact should look that
        contact up in the identity store, and then send it to the addresses
        found in the identity store through Junebug.'''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_outgoing(
            self.unicef, self.user1, None, 'B', "That's great", bob)

        def junebug_callback(request):
            data = json.loads(request.body)
            self.assertEqual(data, {
                'to': '+1234', 'from': None, 'content': "That's great"})
            headers = {'Content-Type': 'application/json'}
            resp = {
                'status': 201,
                'code': 'created',
                'description': 'message submitted',
                'result': {
                    'id': 'message-uuid-1234',
                },
            }
            return (201, headers, json.dumps(resp))
        responses.add_callback(
            responses.POST,
            'http://localhost:8080/channels/replace-me/messages/',
            callback=junebug_callback, content_type='application/json')

        def identity_store_callback(request):
            headers = {'Content-Type': 'application/json'}
            resp = {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "address": "+1234"
                    }
                ]
            }
            return (201, headers, json.dumps(resp))
        responses.add_callback(
            responses.GET,
            'http://localhost:8081/api/v1/identities/%s/addresses/msisdn' % (
                bob.uuid),
            callback=identity_store_callback, content_type='application/json')

        self.backend.push_outgoing(self.unicef, [msg])
        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    @override_settings(JUNEBUG_FROM_ADDRESS='+4321')
    def test_outgoing_from_address(self):
        '''Setting the from address in the settings should set the from address
        in the request to Junebug.'''
        self.backend = JunebugBackend()
        msg = self.create_outgoing(
            self.unicef, self.user1, None, 'B', "That's great", None,
            urn="tel:+1234")

        def request_callback(request):
            data = json.loads(request.body)
            self.assertEqual(data, {
                'to': '+1234', 'from': '+4321', 'content': "That's great"})
            headers = {'Content-Type': 'application/json'}
            resp = {
                'status': 201,
                'code': 'created',
                'description': 'message submitted',
                'result': {
                    'id': 'message-uuid-1234',
                },
            }
            return (201, headers, json.dumps(resp))
        responses.add_callback(
            responses.POST,
            'http://localhost:8080/channels/replace-me/messages/',
            callback=request_callback, content_type='application/json')

        self.backend.push_outgoing(self.unicef, [msg])
        self.assertEqual(len(responses.calls), 1)

    def test_outgoing_no_urn_no_contact(self):
        '''If the outgoing message has no URN or contact, then we cannot send
        it.'''
        msg = self.create_outgoing(
            self.unicef, self.user1, None, 'B', "That's great", None,
            urn=None)

        self.assertRaises(
            JunebugMessageSendingError, self.backend.push_outgoing,
            self.unicef, [msg])

    def test_outgoing_invalid_urn(self):
        '''If the outgoing message has an invalid URN, an exception should be
        raised.'''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_outgoing(
            self.unicef, self.user1, None, 'B', "That's great", bob,
            urn='badurn')

        self.assertRaises(
            JunebugMessageSendingError, self.backend.push_outgoing,
            self.unicef, [msg])

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


class IdentityStoreTest(BaseCasesTest):
    @responses.activate
    def test_get_addresses(self):
        '''The get_addresses function should call the correct URL, and return
        the relevant addresses.'''
        identity_store = IdentityStore(
            'http://identitystore.org/', 'auth-token', 'msisdn')

        def request_callback(request):
            self.assertEqual(
                request.headers.get('Content-Type'), 'application/json')
            self.assertEqual(
                request.headers.get('Authorization'), 'Token auth-token')
            headers = {'Content-Type': 'application/json'}
            resp = {
                "count": 2,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "address": "+4321"
                    },
                    {
                        "address": "+1234"
                    }
                ]
            }
            return (201, headers, json.dumps(resp))
        responses.add_callback(
            responses.GET,
            'http://identitystore.org/api/v1/identities/identity-uuid/'
            'addresses/msisdn?default=True', match_querystring=True,
            callback=request_callback, content_type='application/json')

        res = identity_store.get_addresses('identity-uuid')
        self.assertEqual(sorted(res), sorted(['+1234', '+4321']))

    @responses.activate
    def test_get_paginated_response(self):
        '''The get_paginated_response function should follow all the next links
        until it runs out of pages, and return the combined results.'''
        identity_store = IdentityStore(
            'http://identitystore.org/', 'auth-token', 'msisdn')

        def request_callback_1(request):
            headers = {'Content-Type': 'application/json'}
            resp = {
                "count": 5,
                "next": (
                    'http://identitystore.org/api/v1/identities/identity-uuid/'
                    'addresses/msisdn?default=True&limit=2&offset=2'),
                "previous": None,
                "results": [
                    {
                        "address": "+1111"
                    },
                    {
                        "address": "+2222"
                    }
                ]
            }
            return (201, headers, json.dumps(resp))
        responses.add_callback(
            responses.GET,
            'http://identitystore.org/api/v1/identities/identity-uuid/'
            'addresses/msisdn?default=True', match_querystring=True,
            callback=request_callback_1, content_type='application/json')

        def request_callback_2(request):
            headers = {'Content-Type': 'application/json'}
            resp = {
                "count": 5,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "address": "+3333"
                    },
                ]
            }
            return (201, headers, json.dumps(resp))
        responses.add_callback(
            responses.GET,
            'http://identitystore.org/api/v1/identities/identity-uuid/'
            'addresses/msisdn?default=True&limit=2&offset=2',
            match_querystring=True, callback=request_callback_2,
            content_type='application/json')

        res = identity_store.get_paginated_response(
            ('http://identitystore.org/api/v1/identities/identity-uuid/'
             'addresses/msisdn'), params={'default': True})
        self.assertEqual(sorted(res), sorted([
            {'address': '+1111'},
            {'address': '+2222'},
            {'address': '+3333'},
        ]))
