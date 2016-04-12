from __future__ import unicode_literals

import six

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Contact


@receiver(post_save, sender=Contact)
def update_contact_groups(sender, instance, created, **kwargs):
    """
    Save signal handler to update the contact groups when groups are specified as attribute on the contact object
    """
    if not hasattr(instance, Contact.SAVE_GROUPS_ATTR):
        return

    org = instance.org

    new_groups_by_uuid = {g[0]: g[1] for g in getattr(instance, Contact.SAVE_GROUPS_ATTR)}

    cur_groups_by_uuid = {} if created else {g.uuid: g for g in instance.groups.all()}

    # remove this contact from any groups not in the new set
    remove_from = [g for g in cur_groups_by_uuid.values() if g.uuid not in six.viewkeys(new_groups_by_uuid)]
    if remove_from:
        instance.groups.remove(*remove_from)

    # add this contact to any groups not in the current set
    add_to_by_uuid = {uuid: name for uuid, name in six.iteritems(new_groups_by_uuid)
                      if uuid not in six.viewkeys(cur_groups_by_uuid)}

    if add_to_by_uuid:
        org_groups = {g.uuid: g for g in org.groups.all()}

        # create any groups that don't exist
        add_to_groups = []
        for uuid, name in six.iteritems(add_to_by_uuid):
            existing = org_groups.get(uuid)
            if not existing:
                # create stub
                existing = org.groups.create(uuid=uuid, name=name, is_active=False)

            add_to_groups.append(existing)

        instance.groups.add(*add_to_groups)

    delattr(instance, Contact.SAVE_GROUPS_ATTR)
