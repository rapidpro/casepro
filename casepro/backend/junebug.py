from django.conf import settings
import requests

from . import BaseBackend


class JunebugMessageSendingError(Exception):
    '''Exception that is raised when errors occur when trying to send messages
    through Junebug.'''


class JunebugMessageSender(object):
    def __init__(self, base_url, channel_id, from_address):
        self.base_url = base_url
        self.channel_id = channel_id
        self.from_address = from_address
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
        if not message.urn:
            # If we don't have an URN for a message, we cannot send it, because
            # we don't have an address to send it to.
            # TODO: Add sending to contacts with Identity Store integration.
            raise JunebugMessageSendingError(
                'Cannot send message without URN: %r' % message)
        _, to_addr = self.split_urn(message.urn)
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
        self.message_sender = JunebugMessageSender(
            settings.JUNEBUG_API_ROOT, settings.JUNEBUG_CHANNEL_ID,
            settings.JUNEBUG_FROM_ADDRESS)

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
        return (0, 0, 0, 0)

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
