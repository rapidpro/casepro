from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Label, Message


@receiver(post_save, sender=Label)
def update_label_uuid(sender, instance, **kwargs):
    if instance.is_synced and not instance.uuid:
        instance.org.get_backend().push_label(instance.org, instance)


@receiver(pre_save, sender=Message)
def update_message_contact(sender, instance, **kwargs):
    from casepro.contacts.models import Contact

    if not hasattr(instance, Message.SAVE_CONTACT_ATTR):
        return

    contact = getattr(instance, Message.SAVE_CONTACT_ATTR)

    instance.contact = Contact.get_or_create(instance.org, contact[0], contact[1])


@receiver(post_save, sender=Message)
def update_message_labels(sender, instance, created, **kwargs):
    """
    Save signal handler to update the message labels when labels are specified as attribute on the message object
    """
    if not hasattr(instance, Message.SAVE_LABELS_ATTR):
        return

    org = instance.org

    new_labels_by_uuid = {l[0]: l[1] for l in getattr(instance, Message.SAVE_LABELS_ATTR)}

    cur_labels_by_uuid = {} if created else {l.uuid: l for l in instance.labels.all() if l.uuid}

    # remove this message from any labels not in the new set
    remove_from = []
    for l in cur_labels_by_uuid.values():
        # don't remove un-synced local labels
        if l.uuid not in new_labels_by_uuid.keys() and l.is_synced:
            remove_from.append(l)

    if remove_from:
        instance.unlabel(*remove_from)

    # add this message to any labels not in the current set
    add_to_by_uuid = {uuid: name for uuid, name in new_labels_by_uuid.items() if uuid not in cur_labels_by_uuid.keys()}
    if add_to_by_uuid:
        org_labels_by_uuid = {l.uuid: l for l in org.labels.all()}
        org_unsynced_names = {l.name for l in org.labels.all() if not l.is_synced}

        # create any labels that don't exist
        add_to_labels = []
        for uuid, name in add_to_by_uuid.items():
            label = org_labels_by_uuid.get(uuid)
            if not label and name not in org_unsynced_names:
                # create stub
                label = org.labels.create(uuid=uuid, name=name, is_active=False)

            if label and label.is_synced:
                add_to_labels.append(label)

        instance.label(*add_to_labels)

    delattr(instance, Message.SAVE_LABELS_ATTR)
