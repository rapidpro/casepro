from casepro.contacts.models import Contact, Field, Group
from casepro.msgs.models import Label, Message
from casepro.test import BaseCasesTest
from django.conf import settings
from django.test import override_settings, RequestFactory
import json
import responses

from ..junebug import (
    IdentityStore, JunebugBackend, JunebugMessageSendingError, IdentityStoreContactSyncer, IdentityStoreContact,
    received_junebug_message, receive_identity_store_optout)


class JunebugBackendTest(BaseCasesTest):
    def setUp(self):
        super(JunebugBackendTest, self).setUp()
        self.backend = JunebugBackend()

    def add_identity_store_callback(self, query, callback):
        url = 'http://localhost:8081/api/v1/identities/?' + query
        responses.add_callback(
            responses.GET, url, callback=callback, match_querystring=True, content_type='application/json')

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
                        "preferred_language": "eng_NG",
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
                        "preferred_language": "eng_NG",
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

    def identity_store_forgotten_identity_callback(self, request):
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
                        "name": "redacted",
                        "addresses": {},
                        "preferred_language": "redacted",
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
        self.add_identity_store_callback(
            'created_to=2016-03-14T10%3A21%3A00&created_from=2016-03-14T10%3A25%3A00',
            self.identity_store_created_identity_callback
        )

        self.add_identity_store_callback(
            'updated_to=2016-03-14T10%3A21%3A00&updated_from=2016-03-14T10%3A25%3A00',
            self.identity_store_no_matches_callback
        )

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, '2016-03-14T10:25:00', '2016-03-14T10:21:00')
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Contact.objects.count(), 1)
        [contact] = Contact.objects.all()
        self.assertEqual(contact.uuid, "test_id")
        self.assertEqual(contact.name, "test")

    @responses.activate
    def test_pull_contacts_recently_updated(self):
        Contact.get_or_create(self.unicef, 'test_id', "testing")

        self.add_identity_store_callback(
            'created_to=2016-03-14T10%3A21%3A00&created_from=2016-03-14T10%3A25%3A00',
            self.identity_store_no_matches_callback
        )

        self.add_identity_store_callback(
            'updated_to=2016-03-14T10%3A21%3A00&updated_from=2016-03-14T10%3A25%3A00',
            self.identity_store_updated_identity_callback
        )

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, '2016-03-14T10:25:00', '2016-03-14T10:21:00')
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Contact.objects.count(), 1)
        [contact] = Contact.objects.all()
        self.assertEqual(contact.uuid, "test_id")
        self.assertEqual(contact.name, "test")

    @responses.activate
    def test_pull_contacts_forgotten(self):
        self.add_identity_store_callback(
            'created_to=2016-03-14T10%3A21%3A00&created_from=2016-03-14T10%3A25%3A00',
            self.identity_store_forgotten_identity_callback
        )

        self.add_identity_store_callback(
            'updated_to=2016-03-14T10%3A21%3A00&updated_from=2016-03-14T10%3A25%3A00',
            self.identity_store_forgotten_identity_callback
        )

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, '2016-03-14T10:25:00', '2016-03-14T10:21:00')
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 0)
        self.assertEqual(Contact.objects.count(), 0)

    @responses.activate
    def test_pull_contacts_no_changes(self):
        Contact.objects.create(org=self.unicef, uuid='test_id', name="test", language='eng')

        self.add_identity_store_callback(
            'created_to=2016-03-14T10%3A21%3A00&created_from=2016-03-14T10%3A25%3A00',
            self.identity_store_no_matches_callback
        )

        self.add_identity_store_callback(
            'updated_to=2016-03-14T10%3A21%3A00&updated_from=2016-03-14T10%3A25%3A00',
            self.identity_store_updated_identity_callback
        )

        (created, updated, deleted, ignored) = self.backend.pull_contacts(
            self.unicef, '2016-03-14T10:25:00', '2016-03-14T10:21:00')
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(ignored, 1)
        self.assertEqual(Contact.objects.count(), 1)
        [contact] = Contact.objects.all()
        self.assertEqual(contact.uuid, "test_id")
        self.assertEqual(contact.name, "test")

    def test_pull_fields(self):
        '''
        Pulling all the fields should be a noop.
        '''
        Field.objects.all().delete()

        (created, updated, deleted, ignored) = self.backend.pull_fields(self.unicef)

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

        (created, updated, deleted, ignored) = self.backend.pull_groups(self.unicef)

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

        (created, updated, deleted, ignored) = self.backend.pull_labels(self.unicef)

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

        (created, updated, deleted, ignored) = self.backend.pull_messages(self.unicef, None, None)

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
        Sending outgoing messages with a specified urn should send via Junebug with that URN.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_outgoing(self.unicef, self.user1, None, 'B', "That's great", bob, urn="tel:+1234")

        def request_callback(request):
            data = json.loads(request.body)
            self.assertEqual(data, {'to': '+1234', 'from': None, 'content': "That's great"})
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
            responses.POST, 'http://localhost:8080/channels/replace-me/messages/', callback=request_callback,
            content_type='application/json')

        self.backend.push_outgoing(self.unicef, [msg])
        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_outgoing_contact(self):
        '''
        Sending outgoing message with a specified contact should look that contact up in the identity store, and then
        send it to the addresses found in the identity store through Junebug.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_outgoing(self.unicef, self.user1, None, 'B', "That's great", bob)

        def junebug_callback(request):
            data = json.loads(request.body)
            self.assertEqual(data, {'to': '+1234', 'from': None, 'content': "That's great"})
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
            responses.POST, 'http://localhost:8080/channels/replace-me/messages/', callback=junebug_callback,
            content_type='application/json')

        def identity_address_callback(request):
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
            responses.GET, 'http://localhost:8081/api/v1/identities/%s/addresses/msisdn' % (bob.uuid),
            callback=identity_address_callback, content_type='application/json')

        def identity_callback(request):
            headers = {'Content-Type': 'application/json'}
            resp = {
                "id": bob.uuid,
                "version": 1,
                "details": {
                },
                "communicate_through": None,
                "operator": None,
                "created_at": "2016-06-23T13:03:18.674016Z",
                "created_by": 1,
                "updated_at": "2016-06-23T13:03:18.674043Z",
                "updated_by": 1
            }
            return 200, headers, json.dumps(resp)
        responses.add_callback(
            responses.GET, 'http://localhost:8081/api/v1/identities/%s/' % bob.uuid, callback=identity_callback,
            content_type='application/json')

        self.backend.push_outgoing(self.unicef, [msg])
        self.assertEqual(len(responses.calls), 3)

    @responses.activate
    @override_settings(JUNEBUG_FROM_ADDRESS='+4321')
    def test_outgoing_from_address(self):
        '''
        Setting the from address in the settings should set the from address in the request to Junebug.
        '''
        self.backend = JunebugBackend()
        msg = self.create_outgoing(self.unicef, self.user1, None, 'B', "That's great", None, urn="tel:+1234")

        def request_callback(request):
            data = json.loads(request.body)
            self.assertEqual(data, {'to': '+1234', 'from': '+4321', 'content': "That's great"})
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
            responses.POST, 'http://localhost:8080/channels/replace-me/messages/', callback=request_callback,
            content_type='application/json')

        self.backend.push_outgoing(self.unicef, [msg])
        self.assertEqual(len(responses.calls), 1)

    def test_outgoing_no_urn_no_contact(self):
        '''
        If the outgoing message has no URN or contact, then we cannot send it.
        '''
        msg = self.create_outgoing(self.unicef, self.user1, None, 'B', "That's great", None, urn=None)

        self.assertRaises(JunebugMessageSendingError, self.backend.push_outgoing, self.unicef, [msg])

    def test_outgoing_invalid_urn(self):
        '''
        If the outgoing message has an invalid URN, an exception should be raised.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        msg = self.create_outgoing(self.unicef, self.user1, None, 'B', "That's great", bob, urn='badurn')

        self.assertRaises(JunebugMessageSendingError, self.backend.push_outgoing, self.unicef, [msg])

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
        msg = self.create_message(self.unicef, 123, bob, "Hello", is_archived=True)
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
        msg = self.create_message(self.unicef, 123, bob, "Hello", is_flagged=True)
        self.backend.unflag_messages(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertEqual(msg.is_flagged, True)

    def test_fetch_contact_messages(self):
        '''
        Fetching a list of messages for a contact should be a noop.
        '''
        bob = self.create_contact(self.unicef, 'C-002', "Bob")
        messages = self.backend.fetch_contact_messages(self.unicef, bob, None, None)
        self.assertEqual(messages, [])

    def test_get_url_patterns(self):
        '''
        Should return the list of url patterns needed to receive messages
        from Junebug.
        '''
        urls = self.backend.get_url_patterns()
        self.assertEqual(urls[0].callback, received_junebug_message)
        self.assertEqual(urls[0].regex.pattern, settings.JUNEBUG_INBOUND_URL)
        self.assertEqual(urls[0].name, 'inbound_junebug_message')
        self.assertEqual(urls[1].callback, receive_identity_store_optout)
        self.assertEqual(urls[1].regex.pattern, settings.IDENTITY_STORE_OPTOUT_URL)
        self.assertEqual(urls[1].name, 'identity_store_optout')

        with self.settings(JUNEBUG_INBOUND_URL=r'^test/url/$'):
            urls = self.backend.get_url_patterns()
            self.assertEqual(urls[0].regex.pattern, r'^test/url/$')

        with self.settings(IDENTITY_STORE_OPTOUT_URL=r'^test/url/$'):
            urls = self.backend.get_url_patterns()
            self.assertEqual(urls[1].regex.pattern, r'^test/url/$')


class JunebugInboundViewTest(BaseCasesTest):
    '''
    Tests related to the inbound junebug messages view.
    '''
    url = '/junebug/inbound/'

    def setUp(self):
        self.factory = RequestFactory()
        super(JunebugInboundViewTest, self).setUp()

    def test_method_not_post(self):
        '''
        Only POST requests should be allowed.
        '''
        request = self.factory.get(self.url)
        response = received_junebug_message(request)
        self.assertEqual(json.loads(response.content), {'reason': 'Method not allowed.'})
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_body(self):
        '''
        If the request contains invalid JSON in the body, an appropriate error message and code should be returned.
        '''
        request = self.factory.post(self.url, content_type='application/json', data='{')
        response = received_junebug_message(request)
        self.assertEqual(
            json.loads(response.content), {
                'reason': 'JSON decode error',
                'details': 'Expecting object: line 1 column 1 (char 0)'
            }
        )
        self.assertEqual(response.status_code, 400)

    def create_identity_obj(self, **kwargs):
        defaults = {
            "id": "50d62fcf-856a-489c-914a-56f6e9506ee3",
            "version": 1,
            "details": {
                "addresses": {
                    "msisdn": {
                        "+1234": {}
                    }
                }
            },
            "communicate_through": None,
            "operator": None,
            "created_at": "2016-06-23T13:15:55.580070Z",
            "created_by": 1,
            "updated_at": "2016-06-23T13:15:55.580099Z",
            "updated_by": 1
        }
        defaults.update(kwargs)
        return defaults

    def single_identity_callback(self, request):
        headers = {'Content-Type': 'application/json'}
        data = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [
                self.create_identity_obj(),
            ]
        }
        return (200, headers, json.dumps(data))

    @responses.activate
    def test_inbound_message_identity_exists(self):
        '''
        If the identity exists in the identity store, then we should use that identity to create the message.
        '''
        query = '?details__addresses__msisdn=%2B1234'
        url = '%sapi/v1/identities/search/' % settings.IDENTITY_API_ROOT
        responses.add_callback(
            responses.GET, url + query, callback=self.single_identity_callback, match_querystring=True,
            content_type='application/json')

        request = self.factory.post(
            self.url, content_type='application/json', data=json.dumps({
                'message_id': '35f3336d4a1a46c7b40cd172a41c510d',
                'content': 'test message',
                'from': '+1234',
            })
        )
        request.org = self.unicef
        response = received_junebug_message(request)
        resp_data = json.loads(response.content)

        message = Message.objects.get(backend_id=resp_data['id'])
        self.assertEqual(message.text, 'test message')
        self.assertEqual(message.contact.uuid, "50d62fcf-856a-489c-914a-56f6e9506ee3")

    def create_identity_callback(self, request):
        data = json.loads(request.body)
        self.assertEqual(data.get('details'), {
            'addresses': {
                'msisdn': {
                    '+1234': {},
                },
            },
            'default_addr_type': 'msisdn',
        })
        headers = {'Content-Type': 'application/json'}
        return (201, headers, json.dumps(self.create_identity_obj()))

    def no_identity_callback(self, request):
        headers = {'Content-Type': 'application/json'}
        data = {
            'count': 0,
            'next': None,
            'previous': None,
            'results': []
        }
        return (200, headers, json.dumps(data))

    @responses.activate
    def test_inbound_message_identity_doesnt_exist(self):
        '''
        If the identity doesn't exist in the identity store, then the one should be created.
        '''
        query = '?details__addresses__msisdn=%2B1234'
        get_url = '%sapi/v1/identities/search/' % settings.IDENTITY_API_ROOT
        responses.add_callback(
            responses.GET, get_url + query, callback=self.no_identity_callback, match_querystring=True,
            content_type='application/json')
        create_url = '%sapi/v1/identities/' % settings.IDENTITY_API_ROOT
        responses.add_callback(
            responses.POST, create_url, callback=self.create_identity_callback, match_querystring=True,
            content_type='application/json')

        request = self.factory.post(
            self.url, content_type='application/json', data=json.dumps({
                'message_id': '35f3336d4a1a46c7b40cd172a41c510d',
                'content': 'test message',
                'from': '+1234',
            })
        )
        request.org = self.unicef
        received_junebug_message(request)

        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(responses.calls[1].request.method, 'POST')
        self.assertEqual(responses.calls[1].request.url, create_url)


class IdentityStoreOptoutViewTest(BaseCasesTest):
    '''
    Tests related to the optout identity store view.
    '''
    url = '/junebug/optout/'

    def setUp(self):
        self.factory = RequestFactory()
        super(IdentityStoreOptoutViewTest, self).setUp()

    def test_method_not_post(self):
        '''
        Only POST requests should be allowed.
        '''
        request = self.factory.get(self.url)
        response = receive_identity_store_optout(request)
        self.assertEqual(json.loads(response.content), {'reason': 'Method not allowed.'})
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_body(self):
        '''
        If the request contains invalid JSON in the body, an appropriate error message and code should be returned.
        '''
        request = self.factory.post(self.url, content_type='application/json', data='{')
        response = receive_identity_store_optout(request)
        self.assertEqual(
            json.loads(response.content), {
                'reason': 'JSON decode error',
                'details': 'Expecting object: line 1 column 1 (char 0)'
            }
        )
        self.assertEqual(response.status_code, 400)

    def get_optout_request(self, identity, optout_type):
        request = self.factory.post(
            self.url, content_type='application/json', data=json.dumps({
                'identity': identity,
                'details': {
                    "name": "testing",
                    "addresses": {
                        "msisdn": {
                            "+1234": {}
                        },
                    },
                    "preferred_language": "eng_NG",
                },
                'optout_type': optout_type,
            })
        )
        request.org = self.unicef
        return request

    @responses.activate
    def test_forget_optout_received(self):
        '''
        Forget optouts should unset the contact's is_active flag
        '''
        contact = Contact.get_or_create(self.unicef, 'test_id', "testing")
        self.assertTrue(contact.is_active)

        request = self.get_optout_request(contact.uuid, 'forget')
        response = receive_identity_store_optout(request)
        self.assertEqual(response.content, '{"success": true}')

        # refresh contact from db
        contact = Contact.get_or_create(self.unicef, 'test_id', "testing")
        self.assertFalse(contact.is_active)

    @responses.activate
    def test_stop_optout_received(self):
        '''
        Stop optouts should set the contact's is_blocked flag
        '''
        contact = Contact.get_or_create(self.unicef, 'test_id', "testing")
        self.assertFalse(contact.is_blocked)

        request = self.get_optout_request(contact.uuid, 'stop')
        response = receive_identity_store_optout(request)
        self.assertEqual(response.content, '{"success": true}')

        # refresh contact from db
        contact = Contact.get_or_create(self.unicef, 'test_id', "testing")
        self.assertTrue(contact.is_blocked)

    @responses.activate
    def test_unsubscribe_optout_received(self):
        '''
        Unsubscribe optouts shouldn't change the contact
        '''
        original_contact = Contact.get_or_create(self.unicef, 'test_id', "testing")

        request = self.get_optout_request(original_contact.uuid, 'unsubscribe')
        response = receive_identity_store_optout(request)
        self.assertEqual(response.content, '{"success": true}')

        # refresh contact from db
        new_contact = Contact.get_or_create(self.unicef, 'test_id', "testing")
        self.assertEqual(original_contact.is_active, new_contact.is_active)
        self.assertEqual(original_contact.is_blocked, new_contact.is_blocked)

    @responses.activate
    def test_unrecognised_optout_received(self):
        '''
        Unrecognised optouts should return an error
        '''
        original_contact = Contact.get_or_create(self.unicef, 'test_id', "testing")

        request = self.get_optout_request(original_contact.uuid, 'unrecognised')
        response = receive_identity_store_optout(request)
        self.assertEqual(
            json.loads(response.content),
            {'reason': "Unrecognised value for 'optout_type': unrecognised"})
        self.assertEqual(response.status_code, 400)

    @responses.activate
    def test_optout_received_no_contact(self):
        '''
        Optouts received for non-existant contacts should return an error
        '''
        Contact.get_or_create(self.unicef, 'test_id', "testing")

        request = self.get_optout_request('tester', 'forget')
        response = receive_identity_store_optout(request)
        self.assertEqual(json.loads(response.content), {'reason': "No Contact for id: tester"})
        self.assertEqual(response.status_code, 400)

    @responses.activate
    def test_optout_received_fields_missing(self):
        '''
        Optouts received with fields missing should return an error
        '''
        request = self.factory.post(
            self.url, content_type='application/json', data=json.dumps({
                'details': {
                    "name": "testing",
                    "addresses": {
                        "msisdn": {
                            "+1234": {}
                        },
                    },
                    "preferred_language": "eng_NG",
                },
            })
        )
        response = receive_identity_store_optout(request)
        self.assertEqual(
            json.loads(response.content),
            {'reason': 'Both "identity" and "optout_type" must be specified.'})
        self.assertEqual(response.status_code, 400)


class IdentityStoreTest(BaseCasesTest):
    def get_identities_callback(self, request):
        self.assertEqual(request.headers.get('Content-Type'), 'application/json')
        self.assertEqual(request.headers.get('Authorization'), 'Token auth-token')
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
                        "preferred_language": "eng_NG",
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
    def test_get_addresses(self):
        '''
        The get_addresses function should call the correct URL, and return
        the relevant addresses.
        '''
        identity_store = IdentityStore('http://identitystore.org/', 'auth-token', 'msisdn')

        def request_callback(request):
            self.assertEqual(request.headers.get('Content-Type'), 'application/json')
            self.assertEqual(request.headers.get('Authorization'), 'Token auth-token')
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
            responses.GET, 'http://identitystore.org/api/v1/identities/identity-uuid/' 'addresses/msisdn?default=True',
            match_querystring=True, callback=request_callback, content_type='application/json')

        def identity_callback(request):
            headers = {'Content-Type': 'application/json'}
            resp = {
                "id": "identity-uuid",
                "version": 1,
                "details": {
                },
                "communicate_through": None,
                "operator": None,
                "created_at": "2016-06-23T13:03:18.674016Z",
                "created_by": 1,
                "updated_at": "2016-06-23T13:03:18.674043Z",
                "updated_by": 1
            }
            return 200, headers, json.dumps(resp)
        responses.add_callback(
            responses.GET, 'http://identitystore.org/api/v1/identities/identity-uuid/', callback=identity_callback,
            content_type='application/json')

        res = identity_store.get_addresses('identity-uuid')
        self.assertEqual(sorted(res), sorted(['+1234', '+4321']))

    @responses.activate
    def test_get_addresses_communicate_through(self):
        '''
        If the identity has a communicate_through parameter, we should get
        the addresses of that identity instead of the current one.
        '''
        identity_store = IdentityStore('http://identitystore.org/', 'auth-token', 'msisdn')

        def addresses_callback(request):
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
            return 200, headers, json.dumps(resp)
        responses.add_callback(
            responses.GET, 'http://identitystore.org/api/v1/identities/other-uuid/' 'addresses/msisdn?default=True',
            match_querystring=True, callback=addresses_callback, content_type='application/json')

        def other_identity_callback(request):
            headers = {'Content-Type': 'application/json'}
            resp = {
                "id": "other-uuid",
                "version": 1,
                "details": {
                },
                "communicate_through": None,
                "operator": None,
                "created_at": "2016-06-23T13:03:18.674016Z",
                "created_by": 1,
                "updated_at": "2016-06-23T13:03:18.674043Z",
                "updated_by": 1
            }
            return 200, headers, json.dumps(resp)
        responses.add_callback(
            responses.GET, 'http://identitystore.org/api/v1/identities/other-uuid/', callback=other_identity_callback,
            content_type='application/json')

        def identity_callback(request):
            headers = {'Content-Type': 'application/json'}
            resp = {
                "id": "identity-uuid",
                "version": 1,
                "details": {
                },
                "communicate_through": "other-uuid",
                "operator": None,
                "created_at": "2016-06-23T13:03:18.674016Z",
                "created_by": 1,
                "updated_at": "2016-06-23T13:03:18.674043Z",
                "updated_by": 1
            }
            return 200, headers, json.dumps(resp)
        responses.add_callback(
            responses.GET, 'http://identitystore.org/api/v1/identities/identity-uuid/', callback=identity_callback,
            content_type='application/json')

        res = identity_store.get_addresses('identity-uuid')
        self.assertEqual(sorted(res), sorted(['+1234', '+4321']))

    @responses.activate
    def test_get_identities(self):
        '''
        The get_identities function should call the correct URL, and return the relevant identities.
        '''
        identity_store = IdentityStore('http://identitystore.org/', 'auth-token', 'msisdn')

        responses.add_callback(
            responses.GET, 'http://identitystore.org/api/v1/identities/?details__name=test', match_querystring=True,
            callback=self.get_identities_callback, content_type='application/json')

        [identity] = identity_store.get_identities(details__name="test")
        self.assertEqual(identity.name, "test")

    @responses.activate
    def test_get_paginated_response(self):
        '''
        The get_paginated_response function should follow all the next links until it runs out of pages, and return the
        combined results.
        '''
        identity_store = IdentityStore('http://identitystore.org/', 'auth-token', 'msisdn')

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
            responses.GET, 'http://identitystore.org/api/v1/identities/identity-uuid/addresses/msisdn?default=True',
            match_querystring=True, callback=request_callback_1, content_type='application/json')

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
            responses.GET, 'http://identitystore.org/api/v1/identities/identity-uuid/'
            'addresses/msisdn?default=True&limit=2&offset=2', match_querystring=True, callback=request_callback_2,
            content_type='application/json')

        res = identity_store.get_paginated_response(
            ('http://identitystore.org/api/v1/identities/identity-uuid/' 'addresses/msisdn'), params={'default': True})
        self.assertEqual(sorted(res), sorted([
            {'address': '+1111'},
            {'address': '+2222'},
            {'address': '+3333'},
        ]))

    def create_identity_obj(self, **kwargs):
        defaults = {
            "id": "50d62fcf-856a-489c-914a-56f6e9506ee3",
            "version": 1,
            "details": {
                "addresses": {
                    "msisdn": {
                        "+1234": {}
                    }
                },
                'default_addr_type': 'msisdn',
            },
            "communicate_through": None,
            "operator": None,
            "created_at": "2016-06-23T13:15:55.580070Z",
            "created_by": 1,
            "updated_at": "2016-06-23T13:15:55.580099Z",
            "updated_by": 1
        }
        defaults.update(kwargs)
        return defaults

    def single_identity_callback(self, request):
        headers = {'Content-Type': 'application/json'}
        data = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [
                self.create_identity_obj(),
            ]
        }
        return (200, headers, json.dumps(data))

    @responses.activate
    def test_get_identities_for_address(self):
        '''
        The get_identities_for_address to create the correct request to list all of the identities for a specified
        address and address type.
        '''
        identity_store = IdentityStore('http://identitystore.org/', 'auth-token', 'msisdn')

        query = '?details__addresses__msisdn=%2B1234'
        url = 'http://identitystore.org/api/v1/identities/search/'
        responses.add_callback(
            responses.GET, url + query, callback=self.single_identity_callback, match_querystring=True,
            content_type='application/json')

        [identity] = identity_store.get_identities_for_address('+1234')
        self.assertEqual(identity['details']['addresses']['msisdn'], {'+1234': {}})

    def create_identity_callback(self, request):
        data = json.loads(request.body)
        self.assertEqual(data.get('details'), {
            'addresses': {
                'msisdn': {
                    '+1234': {},
                },
            },
            'default_addr_type': 'msisdn',
        })
        headers = {'Content-Type': 'application/json'}
        return (201, headers, json.dumps(self.create_identity_obj()))

    @responses.activate
    def test_create_identity(self):
        '''
        The create_identity method should make the correct request to create an identity with the correct details in the
        identity store.
        '''
        identity_store = IdentityStore('http://identitystore.org/', 'auth-token', 'msisdn')

        url = 'http://identitystore.org/api/v1/identities/'
        responses.add_callback(
            responses.POST, url, callback=self.create_identity_callback, match_querystring=True,
            content_type='application/json')

        identity = identity_store.create_identity('+1234')
        self.assertEqual(identity['details'], {
            'addresses': {
                'msisdn': {
                    '+1234': {},
                },
            },
            'default_addr_type': 'msisdn',
        })

    def identity_404_callback(self, request):
        return (404, {'Content-Type': 'application/json'}, {
            "detail": "Not found."
        })

    @responses.activate
    def test_get_identity_404(self):
        '''
        If the Identity does not exist, causing the Identity Store to return a 404, the get_indentity function should
        return None.
        '''
        identity_store = IdentityStore('http://identitystore.org/', 'auth-token', 'msisdn')

        url = 'http://identitystore.org/api/v1/identities/identity-uuid/'
        responses.add_callback(
            responses.GET, url, callback=self.identity_404_callback, match_querystring=True,
            content_type='application/json')

        identity = identity_store.get_identity('identity-uuid')
        self.assertEqual(identity, None)


class IdentityStoreContactTest(BaseCasesTest):
    def test_contact_with_defaults(self):
        identity_data = {
            "id": "test_id",
            "version": 1,
            "details": {
                "addresses": {},
            },
            "communicate_through": None,
            "operator": None,
            "created_at": "2016-02-14T10:21:00.258406Z",
            "created_by": 1,
            "updated_at": None,
            "updated_by": None
        }

        identity_contact = IdentityStoreContact(identity_data)
        self.assertEqual(identity_contact.id, "test_id")
        self.assertIsNone(identity_contact.name)
        self.assertIsNone(identity_contact.language)

    def test_contact_with_data(self):
        identity_data = {
            "id": "test_id",
            "version": 1,
            "details": {
                "name": "test",
                "addresses": {
                    "msisdn": {
                        "+1234": {}
                    },
                },
                "preferred_language": "eng_NG",
            },
            "communicate_through": None,
            "operator": None,
            "created_at": "2016-02-14T10:21:00.258406Z",
            "created_by": 1,
            "updated_at": "2016-03-14T10:21:00.258406Z",
            "updated_by": 1
        }

        identity_contact = IdentityStoreContact(identity_data)
        self.assertEqual(identity_contact.id, "test_id")
        self.assertEqual(identity_contact.name, "test")
        self.assertEqual(identity_contact.language, "eng")


class IdentityStoreContactSyncerTest(BaseCasesTest):
    syncer = IdentityStoreContactSyncer()

    def mk_identity_store_contact(self):
        return IdentityStoreContact(
            {
                "id": "test_1",
                "version": "1",
                "details": {
                    "preferred_language": "eng_NG",
                    "name": "test",
                    "addresses": {
                        "msisdn": {
                            "+1234": {}
                        }
                    }
                },
                "communicate_through": None,
                "operator": None,
                "created_at": "2016-03-14T10:21:00.258406Z",
                "created_by": 1,
                "updated_at": "2016-03-14T10:21:00.258441Z",
                "updated_by": 1
            })

    def test_local_kwargs(self):
        kwargs = self.syncer.local_kwargs(self.unicef, self.mk_identity_store_contact())

        self.assertEqual(kwargs, {
            "org": self.unicef,
            "uuid": "test_1",
            "name": "test",
            "language": "eng",
            "is_blocked": False,
            "is_stub": False,
            "fields": {},
            '__data__groups': {},
        })

    def test_update_required_on_stub(self):
        # create stub contact
        local = Contact.get_or_create(self.unicef, "test_id", "test")

        self.assertTrue(self.syncer.update_required(local, self.mk_identity_store_contact(), {}))

    def test_no_update_required(self):
        local = Contact.objects.create(org=self.unicef, uuid='test_id', name="test", language='eng')
        self.assertFalse(self.syncer.update_required(local, self.mk_identity_store_contact(), {}))

    def test_update_required_name_different(self):
        local = Contact.objects.create(org=self.unicef, uuid='test_id', name="test_1", language='eng')
        self.assertTrue(self.syncer.update_required(local, self.mk_identity_store_contact(), {}))

    def test_update_required_language_different(self):
        local = Contact.objects.create(org=self.unicef, uuid='test_id', name="test", language='ita')
        self.assertTrue(self.syncer.update_required(local, self.mk_identity_store_contact(), {}))

    def test_update_required_groups_different(self):
        '''
        If the list of groups on the local contact differs from the list of groups on the remote contact, an update
        should be required.
        '''
        local = Contact.objects.create(org=self.unicef, uuid='test_id', name='test', language='eng')
        local.groups.create(org=self.unicef, uuid='group_id', name='testgroup')
        self.assertTrue(self.syncer.update_required(local, self.mk_identity_store_contact(), {}))

    def test_delete_local(self):
        '''
        Deleting the local copy of the contact should deactivate it.
        '''
        local = Contact.objects.create(org=self.unicef, uuid='test_id', name='test', language='eng')

        self.assertTrue(local.is_active)

        self.syncer.delete_local(local)

        local.refresh_from_db()
        self.assertFalse(local.is_active)
