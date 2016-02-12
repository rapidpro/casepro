from __future__ import unicode_literals

import six

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Contact, Group, Field, Value, SAVE_GROUPS_ATTR, SAVE_FIELDS_ATTR, CONTACT_LOCK_GROUPS


@receiver(post_save, sender=Contact)
def update_contact_groups(sender, instance, created, **kwargs):
    """
    Save signal handler to update the contact groups when groups are specified as attribute on contact object
    """
    if not hasattr(instance, SAVE_GROUPS_ATTR):
        return

    new_groups_by_uuid = {g[0]: g[1] for g in getattr(instance, SAVE_GROUPS_ATTR)}

    with instance.lock(CONTACT_LOCK_GROUPS):
        cur_groups_by_uuid = {} if created else {g.uuid: g for g in instance.groups.all()}

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
                    # create stub
                    existing = Group.objects.create(org=instance.org, uuid=uuid, name=name, is_active=False)

                add_to_groups.append(existing)

            instance.groups.add(*add_to_groups)

    delattr(instance, SAVE_GROUPS_ATTR)


@receiver(post_save, sender=Contact)
def update_contact_fields(sender, instance, created, **kwargs):
    """
    Save signal handler to update the contact fields when fields are specified as attribute on contact object
    """
    if not hasattr(instance, SAVE_FIELDS_ATTR):
        return

    org = instance.org

    new_values_by_key = getattr(instance, SAVE_FIELDS_ATTR)
    cur_values_by_key = {v.field.key: v for v in instance.values.all()}

    delete_value_ids = []

    for key, val in six.iteritems(new_values_by_key):
        existing_value = cur_values_by_key.get(key)

        if existing_value:
            if val is None:
                delete_value_ids.append(existing_value.pk)
            elif existing_value.get_value() != val:
                existing_value.string_value = val
                existing_value.save(update_fields=('string_value',))
        else:
            field = Field.objects.filter(org=org, key=key).first()
            if not field:
                # create stub
                field = Field.objects.create(org=org, key=key, is_active=False)

            Value.objects.create(contact=instance, field=field, string_value=val)

    # delete any values whose keys don't exist in the new set
    delete_value_ids += [val.pk for key, val in six.iteritems(cur_values_by_key) if key not in six.viewkeys(new_values_by_key)]

    if delete_value_ids:
        Value.objects.filter(pk__in=delete_value_ids).delete()

    delattr(instance, SAVE_FIELDS_ATTR)
