from __future__ import unicode_literals

from math import ceil

from django.core.management.base import BaseCommand
from casepro.cases.models import Case, CaseAction
from casepro.statistics.models import datetime_to_date, DailyCount


def calculate_totals_for_cases(case_id, progress_callback=None):
    qs = Case.objects
    if case_id is not None:
        qs = qs.filter(id__gte=case_id)
    else:
        qs = qs.all()
    # ensure ordering
    qs = qs.order_by('id')
    for case in qs:
        open_action = case.actions.filter(action=CaseAction.OPEN).first()
        org = open_action.case.org
        user = open_action.created_by
        partner = open_action.case.assignee
        case = open_action.case

        day = datetime_to_date(open_action.created_on, org)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_OPENED, org, user)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_OPENED, partner)

        try:
            # only check the first close action, don't count reopens
            close_action = case.actions.filter(action=CaseAction.CLOSE).earliest('created_on')
            DailyCount.record_item(day, DailyCount.TYPE_CASE_CLOSED,
                                   close_action.case.org, close_action.created_by)
            DailyCount.record_item(day, DailyCount.TYPE_CASE_CLOSED, close_action.case.assignee)
        except CaseAction.DoesNotExist:
            # no close action means to close totals to count for this case
            pass

        if progress_callback is not None:
            progress_callback(case.id)


class Command(BaseCommand):
    help = (
        "Calculate the case closed and opened totals for existing data")
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
