from __future__ import unicode_literals

"""
Sync support for contacts, groups and fields
"""

import logging
import six

from casepro.utils import is_dict_equal
from dash.utils import intersection
from temba_client.v1.types import Contact as TembaContact


logger = logging.getLogger(__name__)


def sync_local_to_incoming(org, model, incoming_objects):
    """
    Syncs an org's entire set of local instances of a model to match the set of incoming objects. Requires that the
    local model define the following class methods:

        def sync_identity(cls, instance) - returns the unique identifier of the given local or incoming object
        def sync_get_kwargs(org, incoming) - returns kwargs used to create new local instance or update existing
        def sync_update_required(cls, local, incoming) - returns whether the local instance differs from the incoming

    :param org: the org
    :param model: the local model
    :param incoming_objects: the set of incoming objects
    :return: tuple of number of local objects created, updated and deleted
    """
    num_created = 0
    num_updated = 0
    num_deleted = 0

    existing_by_identity = {model.sync_identity(g): g for g in model.objects.filter(org=org)}
    synced_identifiers = set()

    # any local active objects that need deactivated
    invalid_existing_ids = []

    for incoming in incoming_objects:
        existing = existing_by_identity.get(model.sync_identity(incoming))

        # derive kwargs for the local model (none returned here means don't keep)
        local_kwargs = model.sync_get_kwargs(org, incoming)

        # item exists locally
        if existing:
            existing.org = org  # saves pre-fetching since we already have the org

            if local_kwargs:
                if model.sync_update_required(existing, incoming) or not existing.is_active:
                    for field, value in six.iteritems(local_kwargs):
                        setattr(existing, field, value)

                    existing.is_active = True
                    existing.save()
                    num_updated += 1

            elif existing.is_active:
                invalid_existing_ids.append(existing.pk)
                num_deleted += 1

        elif local_kwargs:
            model.objects.create(**local_kwargs)
            num_created += 1

        synced_identifiers.add(model.sync_identity(incoming))

    # active local objects which weren't in the remote set need to be deleted
    for existing in existing_by_identity.values():
        if existing.is_active and model.sync_identity(existing) not in synced_identifiers:
            invalid_existing_ids.append(existing.pk)
            num_deleted += 1

    if invalid_existing_ids:
        model.objects.filter(org=org, pk__in=invalid_existing_ids).update(is_active=False)

    return num_created, num_updated, num_deleted


def sync_pull_messages(org, model, modified_after, modified_before, progress_callback=None):
    """
    Pull modified messages from RapidPro and syncs with local messages.
    """
    # TODO this needs to become a proper sync routine once the RapidPro API exposes modified messages

    from casepro.contacts.models import Contact

    client = org.get_temba_client(api_version=2)

    num_synced = 0
    num_created = 0
    num_updated = 0
    num_deleted = 0

    inbox_query = client.get_messages(folder='inbox', after=modified_after, before=modified_before)

    for incoming_batch in inbox_query.iterfetches(retry_on_rate_exceed=True):
        incoming_batch_ids = [m.id for m in incoming_batch]
        existing_by_backend_id = {m.backend_id for m in model.objects.filter(backend_id__in=incoming_batch_ids)}

        for incoming in incoming_batch:
            # check if message already exists
            if incoming.id in existing_by_backend_id:
                continue

            contact = Contact.get_or_create(org, incoming.contact.uuid)

            model.objects.create(org=org,
                                 backend_id=incoming.id,
                                 contact=contact,
                                 type='I' if incoming.type == 'inbox' else 'F',
                                 text=incoming.text,
                                 created_on=incoming.created_on)

            num_created += 1

        num_synced += len(incoming_batch)
        if progress_callback:
            progress_callback(num_synced)

    return num_created, num_updated, num_deleted


def sync_pull_contacts(org, model,
                       modified_after=None, modified_before=None,
                       inc_urns=True, groups=None, fields=None,
                       select_related=(), prefetch_related=(),
                       progress_callback=None):
    """
    Pull modified contacts from RapidPro and syncs with local contacts.

    :param * org: the org
    :param type model: the local contact model
    :param * modified_after: the last time we pulled contacts, if None, sync all contacts
    :param * modified_before: the last time we pulled contacts, if None, sync all contacts
    :param bool inc_urns: whether to compare URNs to determine if local contact differs
    :param [str] groups: the contact group UUIDs used - used to determine if local contact differs
    :param [str] fields: the contact field keys used - used to determine if local contact differs
    :param [str] select_related: select related fields when fetching local contacts
    :param [str] prefetch_related: prefetch related fields when fetching local contacts
    :param * progress_callback: callable for tracking progress - called for each fetch with number of contacts fetched
    :return: tuple containing counts of created, updated and deleted contacts
    """
    client = org.get_temba_client(api_version=2)

    num_synced = 0
    num_created = 0
    num_updated = 0
    num_deleted = 0

    active_query = client.get_contacts(after=modified_after, before=modified_before)

    for incoming_batch in active_query.iterfetches(retry_on_rate_exceed=True):

        # TODO figure out it is still worth fetching the whole batch of contacts here to optimise for the update case,
        # even tho we have to potentially re-fetch below in case contacts were created by the message pulling process

        for incoming in incoming_batch:
            with model.sync_lock(incoming.uuid):
                existing_qs = model.objects.filter(org=org, uuid=incoming.uuid)
                if select_related:
                    existing_qs = existing_qs.select_related(*select_related)
                if prefetch_related:
                    existing_qs = existing_qs.prefetch_related(*prefetch_related)

                existing = existing_qs.first()

                # derive kwargs for the local contact model (none return here means don't keep)
                local_kwargs = model.sync_get_kwargs(org, incoming)

                # contact exists locally
                if existing:
                    existing.org = org  # saves pre-fetching since we already have the org

                    if local_kwargs:
                        diff = temba_compare_contacts(incoming, existing.sync_as_temba(), inc_urns, fields, groups)

                        if diff or not existing.is_active:
                            for field, value in six.iteritems(local_kwargs):
                                setattr(existing, field, value)

                            existing.is_active = True
                            existing.save()
                            num_updated += 1

                    elif existing.is_active:  # contact exists locally, but shouldn't now to due to model changes
                        existing.release()
                        num_deleted += 1

                elif local_kwargs:
                    model.objects.create(**local_kwargs)
                    num_created += 1

        num_synced += len(incoming_batch)
        if progress_callback:
            progress_callback(num_synced)

    # now get all contacts deleted in RapidPro in the same time window
    deleted_query = client.get_contacts(deleted=True, after=modified_after, before=modified_before)

    # any contact that has been deleted should also be released locally
    for deleted_batch in deleted_query.iterfetches(retry_on_rate_exceed=True):
        for deleted_contact in deleted_batch:
            with model.sync_lock(deleted_contact.uuid):
                local_contact = model.objects.filter(org=org, uuid=deleted_contact.uuid).first()
                if local_contact:
                    local_contact.release()
                    num_deleted += 1

        num_synced += len(deleted_batch)
        if progress_callback:
            progress_callback(num_synced)

    return num_created, num_updated, num_deleted


def temba_compare_contacts(first, second, inc_urns=True, fields=None, groups=None):
    """
    Compares two Temba contacts to determine if there are differences. Returns
    first difference found.
    """
    def uuids(refs):
        return [o.uuid for o in refs]

    if first.uuid != second.uuid:  # pragma: no cover
        raise ValueError("Can't compare contacts with different UUIDs")

    if first.name != second.name:
        return 'name'

    if inc_urns and sorted(first.urns) != sorted(second.urns):
        return 'urns'

    if groups is None and (sorted(uuids(first.groups)) != sorted(uuids(second.groups))):
        return 'groups'
    if groups:
        a = sorted(intersection(uuids(first.groups), groups))
        b = sorted(intersection(uuids(second.groups), groups))
        if a != b:
            return 'groups'

    if not is_dict_equal(first.fields, second.fields, keys=fields, ignore_none_values=True):
        return 'fields'

    return None


def temba_merge_contacts(first, second, mutex_group_sets):
    """
    Merges two Temba contacts, with priority given to the first contact.
    :param first: the first contact (has priority)
    :param second: the second contact
    :param mutex_group_sets: a list of lists of group UUIDs whose membership is mutually exclusive. For example, if a
            groups A and B describe the contact's state, and groups C and D describe their gender, one can pass
            [(A, B), (C, D)] as this parameter's value to ensure that the merged contact is only in group A or B and
            C or D.
    """
    if first.uuid != second.uuid:  # pragma: no cover
        raise ValueError("Can't merge contacts with different UUIDs")

    # URNs are merged by scheme
    first_urns_by_scheme = {u[0]: u[1] for u in [urn.split(':', 1) for urn in first.urns]}
    urns_by_scheme = {u[0]: u[1] for u in [urn.split(':', 1) for urn in second.urns]}
    urns_by_scheme.update(first_urns_by_scheme)
    merged_urns = ['%s:%s' % (scheme, path) for scheme, path in six.iteritems(urns_by_scheme)]

    # fields are simple key based merge
    merged_fields = second.fields.copy()
    merged_fields.update(first.fields)

    # first merge mutually exclusive group sets
    merged_groups = []
    ignore_uuids = set()

    for group_set in mutex_group_sets:
        # find first possible in set from first contact
        for g in first.groups:
            if g.uuid in group_set:
                merged_groups.append(g)
                break
        # if we didn't find one, look at second contact
        else:
            for g in second.groups:
                if g.uuid in group_set:
                    merged_groups.append(g)
                    break

        # ignore all groups in this set from now on
        ignore_uuids.update(group_set)

    # then merge the remaining groups
    for g in first.groups:
        if g.uuid not in ignore_uuids:
            merged_groups.append(g)
            ignore_uuids.add(g.uuid)
    for g in second.groups:
        if g.uuid not in ignore_uuids:
            merged_groups.append(g)
            ignore_uuids.add(g.uuid)

    return TembaContact.create(uuid=first.uuid, name=first.name,
                               urns=merged_urns, fields=merged_fields, groups=merged_groups)
