# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def calculate_totals_for_cases(apps, schema_editor):
    from casepro.cases.models import Case, CaseAction
    from casepro.statistics.models import DailyCount, datetime_to_date

    qs = Case.objects.all().order_by('id')
    for case in qs:
        open_action = case.actions.filter(action=CaseAction.OPEN).first()
        org = open_action.case.org
        user = open_action.created_by
        partner = open_action.case.assignee
        case = open_action.case

        day = datetime_to_date(open_action.created_on, org)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_OPENED, org)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_OPENED, org, user)
        DailyCount.record_item(day, DailyCount.TYPE_CASE_OPENED, partner)

        try:
            # only check the first close action, don't count reopens
            close_action = case.actions.filter(action=CaseAction.CLOSE).earliest('created_on')
            DailyCount.record_item(day, DailyCount.TYPE_CASE_CLOSED, close_action.case.org)
            DailyCount.record_item(day, DailyCount.TYPE_CASE_CLOSED,
                                   close_action.case.org, close_action.created_by)
            DailyCount.record_item(day, DailyCount.TYPE_CASE_CLOSED, close_action.case.assignee)
        except CaseAction.DoesNotExist:
            # no close action means to close totals to count for this case
            pass


def remove_totals_for_cases(apps, schema_editor):
    from casepro.statistics.models import DailyCount
    db_alias = schema_editor.connection.alias
    DailyCount.objects.using(db_alias).filter(item_type=DailyCount.TYPE_CASE_CLOSED).delete()
    DailyCount.objects.using(db_alias).filter(item_type=DailyCount.TYPE_CASE_OPENED).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0007_populate_label_totals'),
        ('cases', '0042_auto_20160805_1003'),
    ]

    operations = [
        # migrations.RunPython(calculate_totals_for_cases, remove_totals_for_cases),
        # the reverse migration is commented out because it could remove data created after this migration was run,
        # so it should only be used when you know it will do what you want it to do
        migrations.RunPython(calculate_totals_for_cases),
    ]
