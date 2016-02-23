from __future__ import unicode_literals

"""
Sync support
"""

import six

from abc import ABCMeta, abstractmethod


class BaseSyncer(object):
    """
    Base class for classes that describe how to synchronize particular local models against data from the RapidPro API
    """
    __metaclass__ = ABCMeta

    model = None

    def identity(self, local_or_remote):
        """
        Gets the unique identity of the local model instance or remote object
        :param local_or_remote: the local model instance or remote object
        :return: the unique identity
        """
        return local_or_remote.uuid

    def fetch_all_local(self, org):
        """
        Fetches all local model instances
        :param org: the org
        :return: the queryset
        """
        return self.model.objects.filter(org=org)

    def fetch_local(self, org, identifier):
        """
        Fetches a local model instance
        :param org: the org
        :param identifier: the unique identifier
        :return: the instance
        """
        return self.fetch_all_local(org).filter(uuid=identifier).first()

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


def sync_local_to_set(org, syncer, remote_objects):
    """
    Syncs an org's entire set of local instances of a model to match the set of remote objects

    :param org: the org
    :param syncer: the syncer implementation
    :param remote_objects: the set of incoming remote objects
    :return: tuple of number of local objects created, updated and deleted
    """
    model = syncer.model
    num_created = 0
    num_updated = 0
    num_deleted = 0

    existing_by_identity = {syncer.identity(g): g for g in syncer.fetch_all_local(org)}
    synced_identifiers = set()

    for incoming in remote_objects:
        existing = existing_by_identity.get(syncer.identity(incoming))

        # derive kwargs for the local model (none returned here means don't keep)
        local_kwargs = syncer.local_kwargs(org, incoming)

        # item exists locally
        if existing:
            existing.org = org  # saves pre-fetching since we already have the org

            if local_kwargs:
                if syncer.update_required(existing, incoming) or not existing.is_active:
                    for field, value in six.iteritems(local_kwargs):
                        setattr(existing, field, value)

                    existing.is_active = True
                    existing.save()
                    num_updated += 1

            elif existing.is_active:
                syncer.delete_local(existing)
                num_deleted += 1

        elif local_kwargs:
            model.objects.create(**local_kwargs)
            num_created += 1

        synced_identifiers.add(syncer.identity(incoming))

    # active local objects which weren't in the remote set need to be deleted
    for existing in existing_by_identity.values():
        if existing.is_active and syncer.identity(existing) not in synced_identifiers:
            syncer.delete_local(existing)
            num_deleted += 1

    return num_created, num_updated, num_deleted


def sync_local_to_changes(org, syncer, fetches, deleted_fetches, progress_callback=None):
    """
    Sync local instances against changed and deleted remote objects

    :param * org: the org
    :param * syncer: the local model syncer
    :param * fetches: an iterator returning fetches of modified remote objects
    :param * deleted_fetches: an iterator returning fetches of deleted remote objects
    :param * progress_callback: callable for tracking progress - called for each fetch with number of contacts fetched
    :return: tuple containing counts of created, updated and deleted local instances
    """
    model = syncer.model
    num_synced = 0
    num_created = 0
    num_updated = 0
    num_deleted = 0

    for fetch in fetches:
        for remote in fetch:
            with syncer.lock(syncer.identity(remote)):
                existing = syncer.fetch_local(org, syncer.identity(remote))

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
                            num_updated += 1

                    elif existing.is_active:  # exists locally, but shouldn't now to due to model changes
                        syncer.delete_local(existing)
                        num_deleted += 1

                elif local_kwargs:
                    model.objects.create(**local_kwargs)
                    num_created += 1

        num_synced += len(fetch)
        if progress_callback:
            progress_callback(num_synced)

    # any item that has been deleted remotely should also be released locally
    for deleted_fetch in deleted_fetches:
        for deleted_remote in deleted_fetch:
            with syncer.lock(syncer.identity(deleted_remote)):
                existing = syncer.fetch_local(org, syncer.identity(deleted_remote))
                if existing:
                    syncer.delete_local(existing)
                    num_deleted += 1

        num_synced += len(deleted_fetch)
        if progress_callback:
            progress_callback(num_synced)

    return num_created, num_updated, num_deleted
