from __future__ import unicode_literals

"""
Sync support
"""

import six

from abc import ABCMeta, abstractmethod
from collections import defaultdict
from enum import Enum


class SyncOutcome(Enum):
    created = 1
    updated = 2
    deleted = 3


class BaseSyncer(object):
    """
    Base class for classes that describe how to synchronize particular local models against data from the RapidPro API
    """
    __metaclass__ = ABCMeta

    model = None
    local_id_attr = 'uuid'
    remote_id_attr = 'uuid'

    def identify_local(self, local):
        """
        Gets the unique identity of the local model instance
        :param local: the local model instance
        :return: the unique identity
        """
        return getattr(local, self.local_id_attr)

    def identify_remote(self, remote):
        """
        Gets the unique identity of the remote object
        :param remote: the remote object
        :return: the unique identity
        """
        return getattr(remote, self.remote_id_attr)

    def lock(self, org, identity):
        """
        Gets a lock on the given identity value
        :param org: the org
        :param identity: the unique identity
        :return: the lock
        """
        return self.model.lock(org, identity)

    def fetch_local(self, org, identity):
        """
        Fetches a local model instance
        :param org: the org
        :param identity: the unique identity
        :return: the instance
        """
        return self.model.objects.filter(org=org).filter(**{self.local_id_attr: identity}).first()

    @abstractmethod
    def local_kwargs(self, org, remote):
        """
        Generates kwargs for creating or updating a local model instance from a remote object
        :param org: the org
        :param remote: the incoming remote object
        :return: the kwargs
        """
        pass

    def update_required(self, local, remote):
        """
        Determines whether local instance differs from the remote object and so needs to be updated
        :param local: the local instance
        :param remote: the remote object
        :return: whether the local instance must be updated
        """
        return True

    def delete_local(self, local):
        """
        Deletes a local instance
        :param local:
        :return:
        """
        local.is_active = False
        local.save(update_fields=('is_active',))


def sync_from_remote(org, syncer, remote):
    """
    Sync local instance against a single remote object

    :param * org: the org
    :param * syncer: the local model syncer
    :param * remote: the remote object
    :return: the outcome (created, updated or deleted)
    """
    identity = syncer.identify_remote(remote)

    with syncer.lock(org, identity):
        existing = syncer.fetch_local(org, identity)

        # derive kwargs for the local model (none return here means don't keep)
        local_kwargs = syncer.local_kwargs(org, remote)

        # exists locally
        if existing:
            existing.org = org  # saves pre-fetching since we already have the org

            if local_kwargs:
                if syncer.update_required(existing, remote) or not existing.is_active:
                    for field, value in six.iteritems(local_kwargs):
                        setattr(existing, field, value)

                    existing.is_active = True
                    existing.save()
                    return SyncOutcome.updated

            elif existing.is_active:  # exists locally, but shouldn't now to due to model changes
                syncer.delete_local(existing)
                return SyncOutcome.deleted

        elif local_kwargs:
            syncer.model.objects.create(**local_kwargs)
            return SyncOutcome.created


def sync_local_to_set(org, syncer, remote_set):
    """
    Syncs an org's entire set of local instances of a model to match the set of remote objects

    :param org: the org
    :param * syncer: the local model syncer
    :param remote_set: the set of remote objects
    :return: tuple of number of local objects created, updated and deleted
    """
    outcome_counts = defaultdict(int)

    remote_identities = set()

    for remote in remote_set:
        outcome = sync_from_remote(org, syncer, remote)
        outcome_counts[outcome] += 1

        remote_identities.add(syncer.identify_remote(remote))

    # active local objects which weren't in the remote set need to be deleted
    active_locals = syncer.model.objects.filter(org=org, is_active=True)
    delete_locals = active_locals.exclude(**{syncer.local_id_attr + '__in': remote_identities})

    for local in delete_locals:
        with syncer.lock(org, syncer.identify_local(local)):
            syncer.delete_local(local)
            outcome_counts[SyncOutcome.deleted] += 1

    return outcome_counts[SyncOutcome.created], outcome_counts[SyncOutcome.updated], outcome_counts[SyncOutcome.deleted]


def sync_local_to_changes(org, syncer, fetches, deleted_fetches, progress_callback=None):
    """
    Sync local instances against iterators of changed and deleted remote objects

    :param * org: the org
    :param * syncer: the local model syncer
    :param * fetches: an iterator returning fetches of modified remote objects
    :param * deleted_fetches: an iterator returning fetches of deleted remote objects
    :param * progress_callback: callable for tracking progress - called for each fetch with number of contacts fetched
    :return: tuple containing counts of created, updated and deleted local instances
    """
    num_synced = 0
    outcome_counts = defaultdict(int)

    for fetch in fetches:
        for remote in fetch:
            outcome = sync_from_remote(org, syncer, remote)
            outcome_counts[outcome] += 1

        num_synced += len(fetch)
        if progress_callback:
            progress_callback(num_synced)

    # any item that has been deleted remotely should also be released locally
    for deleted_fetch in deleted_fetches:
        for deleted_remote in deleted_fetch:
            identity = syncer.identify_remote(deleted_remote)
            with syncer.lock(org, identity):
                existing = syncer.fetch_local(org, identity)
                if existing:
                    syncer.delete_local(existing)
                    outcome_counts[SyncOutcome.deleted] += 1

        num_synced += len(deleted_fetch)
        if progress_callback:
            progress_callback(num_synced)

    return outcome_counts[SyncOutcome.created], outcome_counts[SyncOutcome.updated], outcome_counts[SyncOutcome.deleted]
