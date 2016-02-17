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

    @abstractmethod
    def add_to_group(self, contact, group):
        """
        Adds the given contact to a group

        :param contact: the contact
        :param group: the group
        """
        pass

    @abstractmethod
    def remove_from_group(self, contact, group):
        """
        Removes the given contact from a group

        :param contact: the contact
        :param group: the group
        """
        pass

    @abstractmethod
    def stop_runs(self, contact):
        """
        Stops any ongoing flow runs for the given contact

        :param contact: the contact
        """
        pass

    def archive_contact_messages(self, contact):
        """
        Archives messages for the given contact

        :param contact: the contact
        """
        pass
