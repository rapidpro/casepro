from __future__ import unicode_literals

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from casepro.msgs.models import Message, Label, Outgoing
from casepro.cases.models import CaseAction

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
