from django.conf import settings
import requests

from . import BaseBackend

from dash.utils import is_dict_equal
from dash.utils.sync import BaseSyncer, sync_local_to_changes

from casepro.contacts.models import Contact
from itertools import chain


class IdentityStore(object):
    '''Implements required methods for accessing the identity data in the
    identity store.'''
    def __init__(self, base_url, auth_token, address_type):
        '''
        base_url: the base URL where the identity store is located
        auth_token: the token that should be used for authorized access
        address_type: the address type of the addresses that we want
        '''
        self.base_url = base_url.rstrip('/')
        self.address_type = address_type
        self.session = requests.Session()
        self.session.headers.update({'Authorization': 'Token %s' % auth_token})
        self.session.headers.update({'Content-Type': 'application/json'})

    def get_paginated_response(self, url, params={}, **kwargs):
        '''Get the results of all pages of a response. Returns an iterator that
        returns each of the items.'''
        while url is not None:
            r = self.session.get(url, params=params, **kwargs)
            data = r.json()
            for result in data.get('results', []):
                yield result
            url = data.get('next', None)
            # params are included in the next url
            params = {}

    def get_addresses(self, uuid):
        '''Get the list of addresses for an identity specified by uuid.'''
        addresses = self.get_paginated_response(
            '%s/api/v1/identities/%s/addresses/%s' % (
                self.base_url, uuid, self.address_type),
            params={'default': True})
        return (
            a['address'] for a in addresses if a.get('address') is not None)

    def get_identities(self, **kwargs):
        '''Get the list of identities filtered by the given kwargs.'''
        url = '%s/api/v1/identities/search/?' % (self.base_url)
        for key, value in kwargs.iteritems():
            url = '%s%s=%s&' % (url, key, value)

        identities = self.get_paginated_response(
            url, params={'default': True})

        return (
            IdentityStoreContact(i) for i in identities if
            i.get('details').get('name') is not "removed"
        )


class IdentityStoreContact(object):
    """
    Holds identity data for syncing
    """
    def __init__(self, json_data):
        for k, v in json_data.items():
            setattr(self, k, v)
        self.name = json_data.get('details').get('name')
        self.addresses = json_data.get('details').get('addresses')


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
            'is_stub': False,
        }

    def update_required(self, local, remote, remote_as_kwargs):
        if local.is_stub or local.name != remote.name:
            return True

        return not is_dict_equal(
            local.get_fields, remote.fields, ignore_none_values=True)


class JunebugMessageSendingError(Exception):
    '''Exception that is raised when errors occur when trying to send messages
    through Junebug.'''


class JunebugMessageSender(object):
    def __init__(self, base_url, channel_id, from_address, identity_store):
        self.base_url = base_url
        self.channel_id = channel_id
        self.from_address = from_address
        self.identity_store = identity_store
        self.session = requests.Session()

    @property
    def url(self):
        return '%s/channels/%s/messages/' % (
            self.base_url.rstrip('/'), self.channel_id)

    def split_urn(self, urn):
        try:
            type_, address = urn.split(':', 1)
        except ValueError:
            raise JunebugMessageSendingError('Invalid URN: %s' % urn)
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
            raise JunebugMessageSendingError(
                'Cannot send message without URN: %r' % message)
        for to_addr in addresses:
            data = {
                'to': to_addr,
                'from': self.from_address,
                'content': message.text,
            }
            self.session.post(self.url, json=data)


class JunebugBackend(BaseBackend):
    '''
    Junebug instance as a backend.
    '''

    def __init__(self):
        self.identity_store = IdentityStore(
            settings.IDENTITY_API_ROOT, settings.IDENTITY_AUTH_TOKEN,
            settings.IDENTITY_ADDRESS_TYPE)
        self.message_sender = JunebugMessageSender(
            settings.JUNEBUG_API_ROOT, settings.JUNEBUG_CHANNEL_ID,
            settings.JUNEBUG_FROM_ADDRESS, self.identity_store)

    def pull_contacts(
            self, org, modified_after, modified_before,
            progress_callback=None):
        """
        Pulls contacts modified in the given time window

        :param org: the org
        :param datetime modified_after: pull contacts modified after this
        :param datetime modified_before: pull contacts modified before this
        :param progress_callback:
            callable that will be called from time to time with number of
            contacts pulled
        :return:
            tuple of the number of contacts created, updated, deleted and
            ignored
        """
        identity_store = self.identity_store

        # all identities created in the Identity Store in the time window
        new_identities = identity_store.get_identities(
            created_at__gte=modified_after, created_at__lte=modified_before)

        # all identities modified in the Identity Store in the time window
        modified_identities = identity_store.get_identities(
            updated_at__gte=modified_after,
            updated_at__lte=modified_before)

        identities_to_update = chain(modified_identities, new_identities)

        # all identities deleted in the Identity Store in the time window
        deleted_identities = identity_store.get_identities(
            optout__optout_type='forget', updated_at__gte=modified_after,
            updated_at__lte=modified_before)

        # the method expects fetches not lists so I faked it
        return sync_local_to_changes(
            org, IdentityStoreContactSyncer(), [identities_to_update],
            [deleted_identities], progress_callback)

    def pull_fields(self, org):
        """
        Pulls all contact fields

        :param org: the org
        :return:
            tuple of the number of fields created, updated, deleted and ignored
        """
        return (0, 0, 0, 0)

    def pull_groups(self, org):
        """
        Pulls all contact groups

        :param org: the org
        :return:
            tuple of the number of groups created, updated, deleted and ignored
        """
        return (0, 0, 0, 0)

    def pull_labels(self, org):
        """
        Pulls all message labels

        :param org: the org
        :return:
            tuple of the number of labels created, updated, deleted and ignored
        """
        return (0, 0, 0, 0)

    def pull_messages(
            self, org, modified_after, modified_before, as_handled=False,
            progress_callback=None):
        """
        Pulls messages modified in the given time window

        :param org: the org
        :param datetime modified_after: pull messages modified after this
        :param datetime modified_before: pull messages modified before this
        :param bool as_handled:
            whether messages should be saved as already handled
        :param progress_callback:
            callable that will be called from time to time with number of
            messages pulled
        :return:
            tuple of the number of messages created, updated, deleted and
            ignored
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
        :param as_broadcast:
            whether outgoing messages differ only by recipient and so can be
            sent as single broadcast
        """
        for message in outgoing:
            self.message_sender.send_message(message)

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
            the messages as JSON objects in reverse chronological order. JSON
            format should match that returned by Message.as_json() for incoming
            messages and Outgoing.as_json() for outgoing messages.
        """
        return []

    def get_url_patterns(self):
        """
        Returns the list of URL patterns that should be registered for this
        backend.

        :return: a list of URL patterns.
        """
        # TODO: Implement views for receiving messages.
        return []
