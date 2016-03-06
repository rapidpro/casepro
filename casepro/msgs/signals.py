from __future__ import unicode_literals

import six

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import Message, SAVE_CONTACT_ATTR, SAVE_LABELS_ATTR


@receiver(pre_save, sender=Message)
def update_message_contact(sender, instance, **kwargs):
    from casepro.contacts.models import Contact

    if not hasattr(instance, SAVE_CONTACT_ATTR):
        return

    contact = getattr(instance, SAVE_CONTACT_ATTR)

    instance.contact = Contact.get_or_create(instance.org, contact[0], contact[1])


@receiver(post_save, sender=Message)
def update_message_labels(sender, instance, created, **kwargs):
    """
    Save signal handler to update the message labels when labels are specified as attribute on the message object
    """
    if not hasattr(instance, SAVE_LABELS_ATTR):
        return

    org = instance.org

    new_labels_by_uuid = {l[0]: l[1] for l in getattr(instance, SAVE_LABELS_ATTR)}

    cur_labels_by_uuid = {} if created else {l.uuid: l for l in instance.labels.all()}

    # remove this contact from any labels not in the new set
    remove_from = [l for l in cur_labels_by_uuid.values() if l.uuid not in six.viewkeys(new_labels_by_uuid)]
    if remove_from:
        instance.labels.remove(*remove_from)

    # add this message to any labels not in the current set
    add_to_by_uuid = {uuid: name for uuid, name in six.iteritems(new_labels_by_uuid)
                      if uuid not in six.viewkeys(cur_labels_by_uuid)}
    if add_to_by_uuid:
        org_labels = {l.uuid: l for l in org.labels.all()}

        # create any labels that don't exist
        add_to_labels = []
        for uuid, name in six.iteritems(add_to_by_uuid):
            existing = org_labels.get(uuid)
            if not existing:
                # create stub
                existing = org.labels.create(uuid=uuid, name=name, is_active=False)

            add_to_labels.append(existing)

        instance.labels.add(*add_to_labels)

    delattr(instance, SAVE_LABELS_ATTR)
