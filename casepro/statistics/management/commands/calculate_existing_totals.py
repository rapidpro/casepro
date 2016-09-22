from __future__ import unicode_literals

from math import ceil

from django.core.management.base import BaseCommand
from django.db import transaction
from casepro.cases.models import Case, CaseAction, Outgoing
from casepro.statistics.models import datetime_to_date, DailySecondTotalCount


def calculate_totals_for_cases(case_id, progress_callback=None):
    qs = Case.objects
    if case_id is not None:
        qs = qs.filter(id__gte=case_id)
    else:
        qs = qs.all()
    # ensure ordering
    qs = qs.order_by('id')
    for case in qs:
        partner = case.assignee

        if case.is_closed:
            # we only consider the first time a case was closed, not any subsequent reopenings
            close_action = case.actions.filter(action=CaseAction.CLOSE).earliest('created_on')
            # calculate time to close at org level
            day = datetime_to_date(close_action.created_on, case.org)
            td = close_action.created_on - case.opened_on
            seconds_since_open = ceil(td.total_seconds())
            DailySecondTotalCount.record_item(day, seconds_since_open,
                                              DailySecondTotalCount.TYPE_TILL_CLOSED, case.org)

            # check if the user who closed the case was from the assigned partner
            if close_action.created_by.partners.filter(id=partner.id).exists():
                # count the time since this case was (re)assigned to this partner
                try:
                    action = case.actions.filter(action=CaseAction.REASSIGN, assignee=partner).latest('created_on')
                    start_date = action.created_on
                except CaseAction.DoesNotExist:
                    start_date = case.opened_on

                td = close_action.created_on - start_date
                seconds_since_open = ceil(td.total_seconds())
                DailySecondTotalCount.record_item(day, seconds_since_open,
                                                  DailySecondTotalCount.TYPE_TILL_CLOSED, partner)

        # check if responded to
        if case.outgoing_messages.exists():
            # count the first reponse at an org level
            first_response = case.outgoing_messages.earliest('created_on')
            day = datetime_to_date(first_response.created_on, case.org)
            td = first_response.created_on - case.opened_on
            seconds_since_open = ceil(td.total_seconds())
            DailySecondTotalCount.record_item(day, seconds_since_open,
                                              DailySecondTotalCount.TYPE_TILL_REPLIED, case.org)
            try:
                first_response = case.outgoing_messages.filter(partner=partner).earliest('created_on')
            except Outgoing.DoesNotExist:
                continue

            day = datetime_to_date(first_response.created_on, case.org)
            # only count the time since this case was (re)assigned to this partner
            try:
                action = case.actions.filter(action=CaseAction.REASSIGN, assignee=partner).latest('created_on')
                start_date = action.created_on
            except CaseAction.DoesNotExist:
                start_date = case.opened_on

            td = first_response.created_on - start_date
            seconds_since_open = ceil(td.total_seconds())
            DailySecondTotalCount.record_item(day, seconds_since_open,
                                              DailySecondTotalCount.TYPE_TILL_REPLIED, partner)

        if progress_callback is not None:
            progress_callback(case.id)


class Command(BaseCommand):
    help = (
        "Calculate the average time to close and reply statistics for existing data")
    verbose = False

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--case',
            dest='case',
            default=None,
            help='A case ID to start processing from incrementally',
        )

    def handle(self, *args, **options):
        def progress_callback(case_id):
            self.stdout.write(" > Processed Case ID: %d" % case_id)

        calculate_totals_for_cases(case_id=options.get('case'), progress_callback=progress_callback)
