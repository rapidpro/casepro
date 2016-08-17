from __future__ import unicode_literals

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from casepro.msgs.models import Message, Label, Outgoing
from casepro.cases.models import Case

from .models import datetime_to_date, DailyCount


@receiver(post_save, sender=Message)
def record_new_incoming(sender, instance, created, **kwargs):
    """
    Records a new outgoing being sent
    """
    if created:
        org = instance.org

        # get day in org timezone
        day = datetime_to_date(instance.created_on, org)

        DailyCount.record_item(day, DailyCount.TYPE_INCOMING, org)


@receiver(post_save, sender=Outgoing)
def record_new_outgoing(sender, instance, created, **kwargs):
    if created and instance.is_reply():
        org = instance.org
        partner = instance.partner
        user = instance.created_by

        # get day in org timezone
        day = datetime_to_date(instance.created_on, org)

        DailyCount.record_item(day, DailyCount.TYPE_REPLIES, org)
        DailyCount.record_item(day, DailyCount.TYPE_REPLIES, org, user)

        if instance.partner:
            DailyCount.record_item(day, DailyCount.TYPE_REPLIES, partner)


@receiver(m2m_changed, sender=Message.labels.through)
def record_incoming_labelling(sender, instance, action, reverse, model, pk_set, **kwargs):
    day = datetime_to_date(instance.created_on, instance.org)

    if action == 'post_add':
        for label_id in pk_set:
            DailyCount.record_item(day, DailyCount.TYPE_INCOMING, Label(pk=label_id))
    elif action == 'post_remove':
        for label_id in pk_set:
            DailyCount.record_removal(day, DailyCount.TYPE_INCOMING, Label(pk=label_id))
    elif action == 'pre_clear':
        for label in instance.labels.all():
            DailyCount.record_removal(day, DailyCount.TYPE_INCOMING, label)


@receiver(post_save, sender=Case)
def record_new_case(sender, instance, created, **kwargs):
    if not created:
        return

    day = datetime_to_date(instance.opened_on, instance.org)
    DailyCount.record_item(day, DailyCount.TYPE_CASE, instance)
