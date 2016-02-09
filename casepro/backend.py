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


class RapidProBackend(BaseBackend):

    def pull_contacts(self, org, modified_after, modified_before, progress_callback=None):
        from casepro.contacts.models import Contact
        from casepro.contacts.sync import sync_pull_contacts  # will move to Dash

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
        from casepro.contacts.sync import sync_pull_groups  # will move to Dash

        return sync_pull_groups(org, Group)

    def pull_fields(self, org):
        from casepro.contacts.models import Field
        from casepro.contacts.sync import sync_pull_fields  # will move to Dash

        return sync_pull_fields(org, Field)