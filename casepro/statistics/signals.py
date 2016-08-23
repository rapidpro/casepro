from __future__ import unicode_literals

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from math import ceil

from casepro.cases.models import CaseAction
from casepro.msgs.models import Message, Label, Outgoing

from .models import datetime_to_date, DailyCount, DailyMinuteTotalCount


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
                DailyMinuteTotalCount.record_item(day, minutes_since_open,
                                                  DailyMinuteTotalCount.TYPE_TILL_REPLIED, org)

            if case.assignee == partner:
                # count the first response by this partner
                if instance == case.outgoing_messages.filter(partner=partner).earliest('created_on'):
                    # only count the time since this case was (re)assigned to this partner
                    try:
                        action = case.actions.filter(action=CaseAction.REASSIGN, assignee=partner).latest('created_on')
                        start_date = action.created_on
                    except CaseAction.DoesNotExist:
                        start_date = case.opened_on

                    td = instance.created_on - start_date
                    minutes_since_open = ceil(td.total_seconds() / 60)
                    DailyMinuteTotalCount.record_item(day, minutes_since_open,
                                                      DailyMinuteTotalCount.TYPE_TILL_REPLIED, partner)


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


@receiver(post_save, sender=CaseAction)
def record_new_case_action(sender, instance, created, **kwargs):
    org = instance.case.org
    user = instance.created_by
    partner = instance.case.assignee
    case = instance.case

    day = datetime_to_date(instance.created_on, instance.case.org)

    if instance.action == CaseAction.CLOSE:
        # count the time to close on an org level
        td = instance.created_on - case.opened_on
        minutes_since_open = ceil(td.total_seconds() / 60)
        DailyMinuteTotalCount.record_item(day, minutes_since_open,
                                          DailyMinuteTotalCount.TYPE_TILL_CLOSED, org)

        if case.assignee == partner:
            # count the time since case was last assigned to this partner till it was closed
            if user.partners.filter(id=partner.id).exists():
                # count the time since this case was (re)assigned to this partner
                try:
                    action = case.actions.filter(action=CaseAction.REASSIGN, assignee=partner).latest('created_on')
                    start_date = action.created_on
                except CaseAction.DoesNotExist:
                    start_date = case.opened_on

                td = instance.created_on - start_date
                minutes_since_open = ceil(td.total_seconds() / 60)
                DailyMinuteTotalCount.record_item(day, minutes_since_open,
                                                  DailyMinuteTotalCount.TYPE_TILL_CLOSED, partner)
