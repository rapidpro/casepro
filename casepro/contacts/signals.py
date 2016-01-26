from __future__ import unicode_literals

import six

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Contact, Group, SAVE_GROUPS_ATTR


@receiver(post_save, sender=Contact)
def update_contact_groups(sender, instance, **kwargs):
    """
    Save signal handler to update the contact groups when groups are specified as attribute on contact object
    """
    if not hasattr(instance, SAVE_GROUPS_ATTR):
        return

    new_groups_by_uuid = {g[0]: g[1] for g in getattr(instance, SAVE_GROUPS_ATTR)}
    cur_groups_by_uuid = {g.uuid: g for g in instance.groups.all()}

    # remove this contact from any groups not in the new set
    remove_from = [g for g in cur_groups_by_uuid.values() if g.uuid not in six.viewkeys(new_groups_by_uuid)]
    if remove_from:
        instance.groups.remove(*remove_from)

    # add this contact to any groups not in the current set
    add_to_by_uuid = {uuid: name for uuid, name in six.iteritems(new_groups_by_uuid) if uuid not in six.viewkeys(cur_groups_by_uuid)}
    if add_to_by_uuid:
        add_to_existing = Group.objects.filter(org=instance.org, uuid__in=six.viewkeys(add_to_by_uuid))
        existing_by_uuid = {g.uuid: g for g in add_to_existing}

        # create any groups that don't exist
        add_to_groups = []
        for uuid, name in six.iteritems(add_to_by_uuid):
            existing = existing_by_uuid.get(uuid)
            if not existing:
                existing = Group.create(instance.org, uuid, name)

            add_to_groups.append(existing)

        instance.groups.add(*add_to_groups)

    del instance.__data__groups
