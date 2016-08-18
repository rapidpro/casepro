from __future__ import unicode_literals

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from math import ceil

from casepro.msgs.models import Message, Label, Outgoing

from .models import datetime_to_date, DailyCount, MinuteTotalCount


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
        case = instance.case

        # get day in org timezone
        day = datetime_to_date(instance.created_on, org)

        DailyCount.record_item(day, DailyCount.TYPE_REPLIES, org)
        DailyCount.record_item(day, DailyCount.TYPE_REPLIES, org, user)

        if instance.partner:
            DailyCount.record_item(day, DailyCount.TYPE_REPLIES, partner)

        if case:
            # count the very first response on an org level
            if instance == case.outgoing_messages.earliest('created_on'):
                td = instance.created_on - case.opened_on
                minutes_since_open = ceil(td.total_seconds() / 60)
                MinuteTotalCount.record_item(minutes_since_open, MinuteTotalCount.TYPE_TILL_REPLIED, org)

            if case.assignee == partner:
                # count the first response by this partner
                if instance == case.outgoing_messages.filter(partner=partner).earliest('created_on'):
                    # only count the time since this case was (re)assigned to this partner
                    action = case.actions.filter(assignee=partner).latest('created_on')
                    td = instance.created_on - action.created_on
                    minutes_since_open = ceil(td.total_seconds() / 60)
                    MinuteTotalCount.record_item(minutes_since_open, MinuteTotalCount.TYPE_TILL_REPLIED, partner)


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
