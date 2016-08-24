from datetime import datetime
from django.conf import settings
from django.conf.urls import url
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import functools
import json
import requests
import pytz

from . import BaseBackend
from ..contacts.models import Contact
from ..msgs.models import Message
from ..utils import uuid_to_int

from dash.utils import is_dict_equal
from dash.utils.sync import BaseSyncer, sync_local_to_changes

from itertools import chain


class IdentityStore(object):
    """Implements required methods for accessing the identity data in the identity store."""
    def __init__(self, base_url, auth_token, address_type):
        """
        base_url: the base URL where the identity store is located
        auth_token: the token that should be used for authorized access
        address_type: the address type of the addresses that we want
        """
        self.base_url = base_url.rstrip("/")
        self.address_type = address_type
        self.session = requests.Session()
        self.session.headers.update({'Authorization': "Token %s" % auth_token})
        self.session.headers.update({'Content-Type': "application/json"})

    def get_paginated_response(self, url, params={}, **kwargs):
        """Get the results of all pages of a response. Returns an iterator that returns each of the items."""
        while url is not None:
            r = self.session.get(url, params=params, **kwargs)
            data = r.json()
            for result in data.get('results', []):
                yield result
            url = data.get('next', None)
            # params are included in the next url
            params = {}

    def get_identity(self, uuid):
        """Returns the details of the identity."""
        r = self.session.get("%s/api/v1/identities/%s/" % (self.base_url, uuid))
        if r.status_code == 404:
            return None
        return r.json()

    def get_addresses(self, uuid):
        """Get the list of addresses that a message to an identity specified by uuid should be sent to."""
        identity = self.get_identity(uuid)
        if identity and identity.get('communicate_through') is not None:
            identity = self.get_identity(identity['communicate_through'])
        addresses = self.get_paginated_response(
            "%s/api/v1/identities/%s/addresses/%s" % (self.base_url, identity['id'], self.address_type),
            params={'default': True})
        return (
            a['address'] for a in addresses if a.get('address') is not None)

    def get_identities_for_address(self, address, address_type=None):
        if address_type is None:
            address_type = self.address_type

        return self.get_paginated_response(
            "%s/api/v1/identities/search/" % (self.base_url),
            params={'details__addresses__%s' % address_type: address})

    def create_identity(self, addresses, name=None, language=None):
        """Creates an identity on the identity store, given the details of the identity."""
        address_dict = {}
        for address in addresses:
            type_, addr = address.split(':', 1)
            address_dict[type_] = {addr: {}}
        identity = self.session.post(
            "%s/api/v1/identities/" % (self.base_url,),
            json={
                'details': {
                    'addresses': address_dict,
                    'default_addr_type': self.address_type,
                    'name': name,
                    'language': language,
                },
            }
        )
        return identity.json()

    def get_identities(self, **params):
        """Get the list of identities filtered by the given kwargs."""
        url = '%s/api/v1/identities/?' % self.base_url

        identities = self.get_paginated_response(url, params=params)

        # Users who opt to be forgotten from the system have their details
        # stored as 'redacted'.
        return (IdentityStoreContact(i) for i in identities if i.get('details').get('name') != "redacted")


class IdentityStoreContact(object):
    """
    Holds identity data for syncing
    """
    def __init__(self, json_data):
        for k, v in json_data.items():
            setattr(self, k, v)

        # Languages in the identity store have the country code at the end
        self.language = None
        remote_language = json_data.get('details').get('preferred_language')
        if remote_language is not None:
            self.language, _, _ = remote_language.partition('_')
        self.name = json_data.get('details').get('name', None)
        self.fields = {}
        self.groups = {}
        addresses = json_data.get('details').get('addresses')
        self.urns = []
        for scheme, address in addresses.items():
            scheme_addresses = []
            for urn, details in address.items():
                if 'optedout' in details and details['optedout'] is True:
                    # Skip opted out URNs
                    continue
                if 'default' in details and details['default'] is True:
                    # If a default is set for the scheme then only store the default
                    scheme_addresses = [urn]
                    break
                scheme_addresses.append(urn)
            for value in scheme_addresses:
                self.urns.append("%s:%s" % (scheme, value))


class IdentityStoreContactSyncer(BaseSyncer):
    """
    Syncer for contacts from the Identity Store
    """
    model = Contact
    remote_id_attr = 'id'

    def local_kwargs(self, org, remote):
        return {
            'org': org,
            'uuid': remote.id,
            'name': remote.name,
            'language': remote.language,
            'is_blocked': False,  # TODO: Get 'is_blocked' from Opt-outs
            'is_stub': False,
            'fields': {},
            Contact.SAVE_GROUPS_ATTR: {},
            'urns': remote.urns,
        }

    def update_required(self, local, remote, remote_as_kwargs):
        if local.is_stub or local.name != remote.name or local.language != remote.language:
            return True

        if {g.uuid for g in local.groups.all()} != {g.uuid for g in remote.groups}:
            return True

        urn_diff = set(local.urns).symmetric_difference(set(remote.urns))
        if urn_diff:
            return True

        return not is_dict_equal(local.get_fields(), remote.fields, ignore_none_values=True)

    def delete_local(self, local):
        local.release()


class JunebugMessageSendingError(Exception):
    """Exception that is raised when errors occur when trying to send messages through Junebug."""


class JunebugMessageSender(object):
    def __init__(self, base_url, channel_id, from_address, identity_store):
        self.base_url = base_url
        self.channel_id = channel_id
        self.from_address = from_address
        self.identity_store = identity_store
        self.session = requests.Session()

    @property
    def url(self):
        return '%s/channels/%s/messages/' % (self.base_url.rstrip('/'), self.channel_id)

    def split_urn(self, urn):
        try:
            type_, address = urn.split(':', 1)
        except ValueError:
            raise JunebugMessageSendingError("Invalid URN: %s" % urn)
        return type_, address

    def send_message(self, message):
        if message.urn:
            _, to_addr = self.split_urn(message.urn)
            addresses = [to_addr]
        elif message.contact and message.contact.uuid:
            uuid = message.contact.uuid
            addresses = self.identity_store.get_addresses(uuid)
        else:
            # If we don't have an URN for a message, we cannot send it.
            raise JunebugMessageSendingError("Cannot send message without URN: %r" % message)
        for to_addr in addresses:
            data = {
                'to': to_addr,
                'from': self.from_address,
                'content': message.text,
            }
            self.session.post(self.url, json=data)


class JunebugBackend(BaseBackend):
    """
    Junebug instance as a backend.
    """

    def __init__(self):
        self.identity_store = IdentityStore(
            settings.IDENTITY_API_ROOT, settings.IDENTITY_AUTH_TOKEN, settings.IDENTITY_ADDRESS_TYPE)
        self.message_sender = JunebugMessageSender(
            settings.JUNEBUG_API_ROOT, settings.JUNEBUG_CHANNEL_ID, settings.JUNEBUG_FROM_ADDRESS, self.identity_store)

    def pull_contacts(self, org, modified_after, modified_before, progress_callback=None):
        """
        Pulls contacts modified in the given time window

        :param org: the org
        :param datetime modified_after: pull contacts modified after this
        :param datetime modified_before: pull contacts modified before this
        :param progress_callback: callable that will be called from time to time with number of contacts pulled
        :return: tuple of the number of contacts created, updated, deleted and ignored
        """
        identity_store = self.identity_store

        # all identities created in the Identity Store in the time window
        new_identities = identity_store.get_identities(created_from=modified_after, created_to=modified_before)

        # all identities modified in the Identity Store in the time window
        modified_identities = identity_store.get_identities(updated_from=modified_after, updated_to=modified_before)

        identities_to_update = list(chain(modified_identities, new_identities))

        # sync_local_to_changes() expects iterables for the 3rd and 4th args
        # Deleted identities are updated via the Identity Store callback
        return sync_local_to_changes(org, IdentityStoreContactSyncer(), [identities_to_update], [], progress_callback)

    def pull_fields(self, org):
        """
        Pulls all contact fields

        :param org: the org
        :return: tuple of the number of fields created, updated, deleted and ignored
        """
        return (0, 0, 0, 0)

    def pull_groups(self, org):
        """
        Pulls all contact groups

        :param org: the org
        :return: tuple of the number of groups created, updated, deleted and ignored
        """
        return (0, 0, 0, 0)

    def pull_labels(self, org):
        """
        Pulls all message labels

        :param org: the org
        :return: tuple of the number of labels created, updated, deleted and ignored
        """
        return (0, 0, 0, 0)

    def pull_messages(self, org, modified_after, modified_before, as_handled=False, progress_callback=None):
        """
        Pulls messages modified in the given time window

        :param org: the org
        :param datetime modified_after: pull messages modified after this
        :param datetime modified_before: pull messages modified before this
        :param bool as_handled: whether messages should be saved as already handled
        :param progress_callback: callable that will be called from time to time with number of messages pulled
        :return: tuple of the number of messages created, updated, deleted and ignored
        """
        return (0, 0, 0, 0)

    def push_label(self, org, label):
        """
        Pushes a new or updated label

        :param org: the org
        :param label: the label
        """

    def push_outgoing(self, org, outgoing, as_broadcast=False):
        """
        Pushes (i.e. sends) outgoing messages

        :param org: the org
        :param outgoing: the outgoing messages
        :param as_broadcast: whether outgoing messages differ only by recipient and so can be sent as single broadcast
        """
        for message in outgoing:
            self.message_sender.send_message(message)

    @staticmethod
    def _identity_equal(identity, contact):
        details = identity.get('details', {})
        for addr in contact.urns:
            addr_type, address = addr.split(':', 1)
            if details.get('addresses', {}).get(addr_type, {}).get(address) is None:
                return False
        if contact.name is not None:
            if details.get('name') != contact.name:
                return False
        if contact.language is not None:
            if details.get('language') != contact.language:
                return False
        return True

    def push_contact(self, org, contact):
        """
        Pushes a new contact. Creates a new contact if one doesn't exist, or assigns UUID of contact if one exists with
        the same details.

        :param org: the org
        :param contact: The contact to create
        """
        if contact.uuid is not None:
            return

        identity_store = IdentityStore(
            settings.IDENTITY_API_ROOT, settings.IDENTITY_AUTH_TOKEN, settings.IDENTITY_ADDRESS_TYPE)
        identities = []
        for urn in contact.urns:
            addr_type, addr = urn.split(':', 1)
            identities.extend(identity_store.get_identities_for_address(addr, addr_type))
        identities = [identity for identity in identities if self._identity_equal(identity, contact)]

        if identities:
            identity = identities[0]
        else:
            identity = identity_store.create_identity(contact.urns, name=contact.name, language=contact.language)
        contact.uuid = identity.get('id')
        contact.save(update_fields=('uuid',))

    def add_to_group(self, org, contact, group):
        """
        Adds the given contact to a group

        :param org: the org
        :param contact: the contact
        :param group: the group
        """

    def remove_from_group(self, org, contact, group):
        """
        Removes the given contact from a group

        :param org: the org
        :param contact: the contact
        :param group: the group
        """

    def stop_runs(self, org, contact):
        """
        Stops any ongoing flow runs for the given contact

        :param org: the org
        :param contact: the contact
        """

    def label_messages(self, org, messages, label):
        """
        Adds a label to the given messages

        :param org: the org
        :param messages: the messages
        :param label: the label
        """

    def unlabel_messages(self, org, messages, label):
        """
        Removes a label from the given messages

        :param org: the org
        :param messages: the messages
        :param label: the label
        """

    def archive_messages(self, org, messages):
        """
        Archives the given messages

        :param org: the org
        :param messages: the messages
        """

    def archive_contact_messages(self, org, contact):
        """
        Archives all messages for the given contact

        :param org: the org
        :param contact: the contact
        """

    def restore_messages(self, org, messages):
        """
        Restores (un-archives) the given messages

        :param org: the org
        :param messages: the messages
        """

    def flag_messages(self, org, messages):
        """
        Flags the given messages

        :param org: the org
        :param messages: the messages
        """

    def unflag_messages(self, org, messages):
        """
        Un-flags the given messages

        :param org: the org
        :param messages: the messages
        """

    def fetch_contact_messages(
            self, org, contact, created_after, created_before):
        """
        Fetches additional messages to display on a case timeline

        :param org: the org
        :param contact: the contact
        :param created_after: include messages created after this time
        :param created_before: include messages created before this time
        :return:
            the messages as JSON objects in reverse chronological order. JSON format should match that returned by
            Message.as_json() for incoming messages and Outgoing.as_json() for outgoing messages.
        """
        return []

    def get_url_patterns(self):
        """
        Returns the list of URL patterns that should be registered for this backend.

        :return: a list of URL patterns.
        """
        return [
            url(settings.JUNEBUG_INBOUND_URL, received_junebug_message, name="inbound_junebug_message"),
            url(settings.IDENTITY_STORE_OPTOUT_URL, receive_identity_store_optout, name="identity_store_optout"),
        ]


def token_auth_required(auth_token_func):
    '''Decorates a function so that token authentication is required to run it'''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            auth_header = request.META.get('HTTP_AUTHORIZATION', None)
            expected_auth_token = auth_token_func()
            if not auth_header:
                response = JsonResponse(
                    {"reason": "Authentication required"}, status=401)
                response['WWW-Authenticate'] = "Token"
                return response
            auth = auth_header.split(" ")
            if auth != ["Token", expected_auth_token]:
                return JsonResponse({"reason": "Forbidden"}, status=403)
            return func(request, *args, **kwargs)

        return wrapper
    return decorator


@csrf_exempt
def received_junebug_message(request):
    """Handles MO messages from Junebug."""
    if request.method != "POST":
        return JsonResponse({'reason': "Method not allowed."}, status=405)

    try:
        data = json.loads(request.body)
    except ValueError as e:
        return JsonResponse({'reason': "JSON decode error", 'details': e.message}, status=400)

    identity_store = IdentityStore(
        settings.IDENTITY_API_ROOT, settings.IDENTITY_AUTH_TOKEN, settings.IDENTITY_ADDRESS_TYPE)
    identities = identity_store.get_identities_for_address(data.get('from'))
    try:
        identity = identities.next()
    except StopIteration:
        identity = identity_store.create_identity(['%s:%s' % (settings.IDENTITY_ADDRESS_TYPE, data.get('from'))])
    contact = Contact.get_or_create(request.org, identity.get('id'))

    message_id = uuid_to_int(data.get('message_id'))
    msg = Message.objects.create(
        org=request.org, backend_id=message_id, contact=contact, type=Message.TYPE_INBOX,
        text=(data.get('content') or ''), created_on=datetime.now(pytz.utc), has_labels=True)

    return JsonResponse(msg.as_json())


def seed_auth_token():
    return settings.IDENTITY_AUTH_TOKEN


@csrf_exempt
@token_auth_required(seed_auth_token)
def receive_identity_store_optout(request):
    """Handles optout notifications from the Identity Store."""
    if request.method != "POST":
        return JsonResponse({'reason': "Method not allowed."}, status=405)

    try:
        data = json.loads(request.body)
    except ValueError as e:
        return JsonResponse({'reason': "JSON decode error", 'details': e.message}, status=400)

    try:
        identity_id = data['identity']
        optout_type = data['optout_type']
    except KeyError as e:
        return JsonResponse({'reason': 'Both "identity" and "optout_type" must be specified.'}, status=400)

    # The identity store currently doesn't specify the response format or do
    # anything with the response.

    syncer = IdentityStoreContactSyncer()
    org = request.org

    with syncer.lock(org, identity_id):
        local_contact = syncer.fetch_local(org, identity_id)
        if not local_contact:
            return JsonResponse({'reason': "No Contact for id: " + identity_id}, status=400)

        if optout_type == "forget":
            # TODO: Removed any identifying details from the contact
            # (to uphold 'Right to be forgotten')
            local_contact.release()
            return JsonResponse({'success': True}, status=200)

        elif optout_type == "stop" or optout_type == "stopall":
            local_contact.is_blocked = True
            local_contact.save(update_fields=("is_blocked",))
            return JsonResponse({'success': True}, status=200)

        elif optout_type == "unsubscribe":
            # This case is not relevant to Casepro
            return JsonResponse({'success': True}, status=200)

    return JsonResponse({'reason': 'Unrecognised value for "optout_type": ' + optout_type}, status=400)
