from abc import ABCMeta, abstractmethod


class BaseBackend(object):
    __metaclass__ = ABCMeta

    def __init__(self, backend):
        self.backend = backend

    @abstractmethod
    def pull_contacts(self, org, modified_after, modified_before, progress_callback=None):
        """
        Pulls contacts modified in the given time window

        :param org: the org
        :param datetime modified_after: pull contacts modified after this
        :param datetime modified_before: pull contacts modified before this
        :param progress_callback: callable that will be called from time to time with number of contacts pulled
        :return: tuple of the number of contacts created, updated, deleted and ignored
        """

    @abstractmethod
    def pull_fields(self, org):
        """
        Pulls all contact fields

        :param org: the org
        :return: tuple of the number of fields created, updated, deleted and ignored
        """

    @abstractmethod
    def pull_groups(self, org):
        """
        Pulls all contact groups

        :param org: the org
        :return: tuple of the number of groups created, updated, deleted and ignored
        """

    @abstractmethod
    def pull_labels(self, org):
        """
        Pulls all message labels

        :param org: the org
        :return: tuple of the number of labels created, updated, deleted and ignored
        """

    @abstractmethod
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

    @abstractmethod
    def push_label(self, org, label):
        """
        Pushes a new or updated label

        :param org: the org
        :param label: the label
        """

    @abstractmethod
    def push_outgoing(self, org, outgoing, as_broadcast=False):
        """
        Pushes (i.e. sends) outgoing messages

        :param org: the org
        :param outgoing: the outgoing messages
        :param as_broadcast: whether outgoing messages differ only by recipient and so can be sent as single broadcast
        """

    @abstractmethod
    def push_contact(self, org, contact):
        """
        Pushes a new contact

        :param org: the org
        :param contact: The contact to create
        """

    @abstractmethod
    def add_to_group(self, org, contact, group):
        """
        Adds the given contact to a group

        :param org: the org
        :param contact: the contact
        :param group: the group
        """

    @abstractmethod
    def remove_from_group(self, org, contact, group):
        """
        Removes the given contact from a group

        :param org: the org
        :param contact: the contact
        :param group: the group
        """

    @abstractmethod
    def stop_runs(self, org, contact):
        """
        Stops any ongoing flow runs for the given contact

        :param org: the org
        :param contact: the contact
        """

    @abstractmethod
    def label_messages(self, org, messages, label):
        """
        Adds a label to the given messages

        :param org: the org
        :param messages: the messages
        :param label: the label
        """

    @abstractmethod
    def unlabel_messages(self, org, messages, label):
        """
        Removes a label from the given messages

        :param org: the org
        :param messages: the messages
        :param label: the label
        """

    @abstractmethod
    def archive_messages(self, org, messages):
        """
        Archives the given messages

        :param org: the org
        :param messages: the messages
        """

    @abstractmethod
    def archive_contact_messages(self, org, contact):
        """
        Archives all messages for the given contact

        :param org: the org
        :param contact: the contact
        """

    @abstractmethod
    def restore_messages(self, org, messages):
        """
        Restores (un-archives) the given messages

        :param org: the org
        :param messages: the messages
        """

    @abstractmethod
    def flag_messages(self, org, messages):
        """
        Flags the given messages

        :param org: the org
        :param messages: the messages
        """

    @abstractmethod
    def unflag_messages(self, org, messages):
        """
        Un-flags the given messages

        :param org: the org
        :param messages: the messages
        """

    @abstractmethod
    def fetch_contact_messages(self, org, contact, created_after, created_before):
        """
        Fetches additional messages to display on a case timeline

        :param org: the org
        :param contact: the contact
        :param created_after: include messages created after this time
        :param created_before: include messages created before this time
        :return: the messages as transient Message and Outgoing instances
        """

    @abstractmethod
    def fetch_flows(self, org):
        """
        Fetches flows which can be used as a follow-up flow

        :param org: the org
        """

    @abstractmethod
    def start_flow(self, org, flow, contact, extra):
        """
        Starts the given contact in the given flow
        :param org:
        :param flow: the flow to start
        :param contact: the contact to start
        :param extra: extra parameters
        """

    @abstractmethod
    def get_url_patterns(self):
        """
        Returns the list of URL patterns that should be registered for this backend.

        :return: a list of URL patterns.
        """


class NoopBackend(BaseBackend):  # pragma: no cover
    """
    A stub backend which doesn't do anything
    """

    NO_CHANGES = (0, 0, 0, 0)

    def pull_contacts(self, org, modified_after, modified_before, progress_callback=None):
        return self.NO_CHANGES

    def pull_fields(self, org):
        return self.NO_CHANGES

    def pull_groups(self, org):
        return self.NO_CHANGES

    def pull_labels(self, org):
        return self.NO_CHANGES

    def pull_messages(self, org, modified_after, modified_before, as_handled=False, progress_callback=None):
        return self.NO_CHANGES

    def fetch_contact_messages(self, org, contact, created_after, created_before):
        return []

    def fetch_flows(self, org):
        return []

    def get_url_patterns(self):
        return []


NoopBackend.__abstractmethods__ = set()
