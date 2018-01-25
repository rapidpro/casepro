from __future__ import unicode_literals

from django.db.models.signals import post_save
from django.dispatch import receiver
from math import ceil

from casepro.cases.models import CaseAction
from casepro.msgs.models import Message, Outgoing

from .models import datetime_to_date, DailyCount, DailySecondTotalCount, record_case_closed_time


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
                seconds_since_open = ceil(td.total_seconds())
                DailySecondTotalCount.record_item(day, seconds_since_open,
                                                  DailySecondTotalCount.TYPE_TILL_REPLIED, org)
            if case.assignee == partner:
                # count the first response by this partner
                if instance == case.outgoing_messages.filter(partner=partner).earliest('created_on'):
                    author_action = case.actions.filter(action=CaseAction.OPEN).order_by('created_on').first()
                    reassign_action = case.actions.filter(
                        action=CaseAction.REASSIGN, assignee=partner).order_by('created_on').first()

                    # don't count self-assigned cases
                    if author_action and author_action.created_by.get_partner(org) != partner:
                        # only count the time since this case was (re)assigned to this partner
                        # or cases that were assigned during creation by another partner
                        if reassign_action:
                            start_date = reassign_action.created_on
                        else:
                            start_date = author_action.created_on

                        td = instance.created_on - start_date
                        seconds_since_open = ceil(td.total_seconds())
                        DailySecondTotalCount.record_item(
                            day, seconds_since_open,
                            DailySecondTotalCount.TYPE_TILL_REPLIED, partner)


@receiver(post_save, sender=CaseAction)
def record_new_case_action(sender, instance, created, **kwargs):
    """
    This is where we keep track of DailyCounts for users within organisations
    """
    org = instance.case.org
    user = instance.created_by
    partner = instance.case.assignee
    case = instance.case

    day = datetime_to_date(instance.created_on, instance.case.org)
    if instance.action == CaseAction.OPEN:
        DailyCount.record_item(day, DailyCount.TYPE_CASE_OPENED, org)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_OPENED, org, user)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_OPENED, partner)

    elif instance.action == CaseAction.CLOSE:
        if case.actions.filter(action=CaseAction.REOPEN).exists():
            # dont count any stats for reopened cases.
            return

        DailyCount.record_item(day, DailyCount.TYPE_CASE_CLOSED, org)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_CLOSED, org, user)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_CLOSED, partner)
        record_case_closed_time(instance)
