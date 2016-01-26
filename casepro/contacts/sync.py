from __future__ import unicode_literals

"""
Contact sync support. This will eventually replace the sync stuff in Dash when API v2 is stable.
"""

import logging
import six

from temba_client.v1.types import Contact as TembaContact
from dash.utils import union, intersection, filter_dict


logger = logging.getLogger(__name__)


def sync_pull_contacts(org, contact_class, inc_urns=True, groups=None, fields=None,
                       last_time=None, delete_blocked=False, prefetch_related=()):
    """
    Pulls updated contacts or all contacts from RapidPro and syncs with local contacts.
    Contact class must define a class method called kwargs_from_temba which generates
    field kwargs from a fetched temba contact.

    :param * org: the org
    :param type contact_class: the contact class type
    :param bool inc_urns: whether to compare URNs to determine if local contact differs
    :param [str] groups: the contact group UUIDs used - used to determine if local contact differs
    :param [str] fields: the contact field keys used - used to determine if local contact differs
    :param * last_time: the last time we pulled contacts, if None, sync all contacts
    :param bool delete_blocked: if True, delete the blocked contacts
    :param [str] prefetch_related: prefetch field when fetching local contacts
    :return: tuple containing counts of created, updated, deleted and failed contacts
    """
    client = org.get_temba_client(api_version=2)

    num_created = 0
    num_updated = 0
    deleted_uuids = []

    for incoming_batch in client.get_contacts(after=last_time).iterfetches(retry_on_rate_exceed=True):
        incoming_uuids = [c.uuid for c in incoming_batch]

        # get all existing contacts with these UUIDs
        existing_contacts = contact_class.objects.filter(org=org, uuid__in=incoming_uuids)

        if prefetch_related:
            existing_contacts.prefetch_related(*prefetch_related)

        # organize by UUID
        existing_by_uuid = {c.uuid: c for c in existing_contacts}

        for incoming in incoming_batch:
            # if blocked and we might consider it deleted locally
            if incoming.blocked and delete_blocked:
                deleted_uuids.append(incoming.uuid)

            # contact exists locally
            elif incoming.uuid in existing_by_uuid:
                existing = existing_by_uuid[incoming.uuid]

                diff = temba_compare_contacts(incoming, existing.as_temba(), inc_urns, fields, groups)

                if diff or not existing.is_active:
                    try:
                        kwargs = contact_class.kwargs_from_temba(org, incoming)
                    except ValueError:
                        logger.warn("Unable to sync contact %s" % incoming.uuid)
                        continue

                    for field, value in six.iteritems(kwargs):
                        setattr(existing, field, value)

                    existing.is_active = True
                    existing.save()

                    num_updated += 1
            else:
                try:
                    kwargs = contact_class.kwargs_from_temba(org, incoming)
                except ValueError:
                    logger.warn("Unable to sync contact %s" % incoming.uuid)
                    continue

                contact_class.objects.create(**kwargs)
                num_created += 1

    # any contact that has been deleted should also be deleted locally
    deleted_incoming = client.get_contacts(deleted=True, after=last_time).all(retry_on_rate_exceed=True)

    for contact in deleted_incoming:
        deleted_uuids.append(contact.uuid)

    num_deleted = contact_class.objects.filter(org=org, uuid__in=deleted_uuids).update(is_active=False)

    return num_created, num_updated, num_deleted


def temba_compare_contacts(first, second, inc_urns=True, fields=None, groups=None):
    """
    Compares two Temba contacts to determine if there are differences. Returns
    first difference found.
    """
    if first.uuid != second.uuid:  # pragma: no cover
        raise ValueError("Can't compare contacts with different UUIDs")

    if first.name != second.name:
        return 'name'

    if inc_urns and sorted(first.urns) != sorted(second.urns):
        return 'urns'

    if groups is None and (sorted(first.groups) != sorted(second.groups)):
        return 'groups'
    if groups:
        a = sorted(intersection(first.groups, groups))
        b = sorted(intersection(second.groups, groups))
        if a != b:
            return 'groups'

    if fields is None and (first.fields != second.fields):
        return 'fields'
    if fields and (filter_dict(first.fields, fields) != filter_dict(second.fields, fields)):
        return 'fields'

    return None


def temba_merge_contacts(first, second, mutex_group_sets):
    """
    Merges two Temba contacts, with priority given to the first contact
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
    first_groups = list(first.groups)
    second_groups = list(second.groups)
    merged_mutex_groups = []
    for group_set in mutex_group_sets:
        from_first = intersection(first_groups, group_set)
        if from_first:
            merged_mutex_groups.append(from_first[0])
        else:
            from_second = intersection(second_groups, group_set)
            if from_second:
                merged_mutex_groups.append(from_second[0])

        for group in group_set:
            if group in first_groups:
                first_groups.remove(group)
            if group in second_groups:
                second_groups.remove(group)

    # then merge the remaining groups
    merged_groups = merged_mutex_groups + union(first_groups, second_groups)

    return TembaContact.create(uuid=first.uuid, name=first.name,
                               urns=merged_urns, fields=merged_fields, groups=merged_groups)
