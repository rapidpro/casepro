from __future__ import unicode_literals

from abc import ABCMeta, abstractmethod
from django.conf import settings
from pydoc import locate


_ACTIVE_BACKEND = None


def get_backend():
    global _ACTIVE_BACKEND
    if not _ACTIVE_BACKEND:
        _ACTIVE_BACKEND = locate(settings.SITE_BACKEND)()
    return _ACTIVE_BACKEND


class BaseBackend(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def pull_contacts(self, org, modified_after, modified_before, progress_callback=None):
        """
        Pulls contacts modified in the given time window
        :param org: the org
        :param datetime modified_after: pull contacts modified after this
        :param datetime modified_before: pull contacts modified before this
        :param progress_callback: callable that will be called from time to time with number of contacts pulled
        :return: tuple of the number of contacts created, updated and deleted
        """
        pass

    @abstractmethod
    def pull_groups(self, org):
        """
        Pulls all contact groups
        :param org: the org
        :return: tuple of the number of groups created, updated and deleted
        """
        pass

    @abstractmethod
    def pull_fields(self, org):
        """
        Pulls all contact fields
        :param org: the org
        :return: tuple of the number of fields created, updated and deleted
        """
        pass

    @abstractmethod
    def pull_and_label_messages(self, org, received_after, received_before, progress_callback=None):
        """
        Pulls and labels messages received in the given time window
        :param org: the org
        :param datetime received_after: pull messages received after this
        :param datetime received_before: pull messages received before this
        :param progress_callback: callable that will be called from time to time with number of messages pulled
        :return: tuple of the the number of messages created, and the number of labels applied
        """
        pass


class RapidProBackend(BaseBackend):
    """
    RapidPro instance as a backend
    """
    def pull_contacts(self, org, modified_after, modified_before, progress_callback=None):
        from casepro.contacts.models import Contact
        from casepro.dash_ext.sync import sync_pull_contacts

        return sync_pull_contacts(
                org, Contact,
                modified_after=modified_after,
                modified_before=modified_before,
                inc_urns=False,
                prefetch_related=('groups', 'values__field'),
                progress_callback=progress_callback
        )

    def pull_groups(self, org):
        from casepro.contacts.models import Group
        from casepro.dash_ext.sync import sync_pull_groups

        return sync_pull_groups(org, Group)

    def pull_fields(self, org):
        from casepro.contacts.models import Field
        from casepro.dash_ext.sync import sync_pull_fields

        return sync_pull_fields(org, Field)

    def pull_and_label_messages(self, org, received_after, received_before, progress_callback=None):
        from casepro.cases.models import RemoteMessage

        client = org.get_temba_client(api_version=2)

        num_messages = 0
        num_labelled = 0

        inbox_query = client.get_messages(folder='inbox', after=received_after, before=received_before)

        for incoming_batch in inbox_query.iterfetches(retry_on_rate_exceed=True):
            num_messages += len(incoming_batch)
            num_labelled += RemoteMessage.process_unsolicited(org, incoming_batch)

        return num_messages, num_labelled
