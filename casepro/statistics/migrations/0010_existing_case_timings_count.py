# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from math import ceil

from django.db import migrations, models


def get_partner(org, user):
    return user.partners.filter(org=org, is_active=True).first()


def calculate_totals_for_cases(apps, schema_editor):
    from casepro.statistics.models import datetime_to_date

    Case = apps.get_model("cases", "Case")
    CaseAction = apps.get_model("cases", "CaseAction")
    Outgoing = apps.get_model("msgs", "Outgoing")
    DailySecondTotalCount = apps.get_model("statistics", "DailySecondTotalCount")

    qs = Case.objects.all().order_by("id")
    for case in qs:
        partner = case.assignee

        if case.closed_on is not None:
            # we only consider the first time a case was closed, not any subsequent reopenings
            close_action = case.actions.filter(action="C").earliest("created_on")
            org = close_action.case.org
            user = close_action.created_by
            partner = close_action.case.assignee
            case = close_action.case

            day = datetime_to_date(close_action.created_on, close_action.case.org)
            # count the time to close on an org level
            td = close_action.created_on - case.opened_on
            seconds_since_open = ceil(td.total_seconds())
            DailySecondTotalCount.objects.create(
                day=day, item_type="C", scope="org:%d" % org.pk, count=1, seconds=seconds_since_open
            )

            # count the time since case was last assigned to this partner till it was closed
            if user.partners.filter(id=partner.id).exists():
                # count the time since this case was (re)assigned to this partner
                try:
                    action = case.actions.filter(action="A", assignee=partner).latest("created_on")
                    start_date = action.created_on
                except CaseAction.DoesNotExist:
                    start_date = case.opened_on

                td = close_action.created_on - start_date
                seconds_since_open = ceil(td.total_seconds())
                DailySecondTotalCount.objects.create(
                    day=day, item_type="C", scope="partner:%d" % partner.pk, count=1, seconds=seconds_since_open
                )

        # check if responded to
        if case.outgoing_messages.exists():
            # count the first reponse at an org level
            first_response = case.outgoing_messages.earliest("created_on")
            day = datetime_to_date(first_response.created_on, case.org)
            td = first_response.created_on - case.opened_on
            seconds_since_open = ceil(td.total_seconds())
            DailySecondTotalCount.objects.create(
                day=day, item_type="A", scope="org:%d" % case.org.pk, count=1, seconds=seconds_since_open
            )
            try:
                first_response = case.outgoing_messages.filter(partner=partner).earliest("created_on")
            except Outgoing.DoesNotExist:
                continue

            day = datetime_to_date(first_response.created_on, case.org)

            # count the first response by this partner
            author_action = case.actions.filter(action="O").order_by("created_on").first()
            reassign_action = case.actions.filter(action="A", assignee=partner).order_by("created_on").first()

            if author_action and get_partner(org, author_action.created_by) != partner:
                # only count the time since this case was (re)assigned to this partner
                # or cases that were assigned during creation by another partner
                if reassign_action:
                    start_date = reassign_action.created_on
                else:
                    start_date = author_action.created_on

                td = first_response.created_on - start_date
                seconds_since_open = ceil(td.total_seconds())
                DailySecondTotalCount.objects.create(
                    day=day, item_type="A", scope="partner:%d" % partner.pk, count=1, seconds=seconds_since_open
                )


def remove_totals_for_cases(apps, schema_editor):
    DailySecondTotalCount = apps.get_model("statistics", "DailySecondTotalCount")
    db_alias = schema_editor.connection.alias
    DailySecondTotalCount.objects.using(db_alias).filter(item_type="A").delete()
    DailySecondTotalCount.objects.using(db_alias).filter(item_type="C").delete()


class Migration(migrations.Migration):

    dependencies = [("statistics", "0009_dailysecondtotalcount"), ("cases", "0042_auto_20160805_1003")]

    operations = [
        # migrations.RunPython(calculate_totals_for_cases, remove_totals_for_cases),
        # the reverse migration is commented out because it could remove data created after this migration was run,
        # so it should only be used when you know it will do what you want it to do
        migrations.RunPython(calculate_totals_for_cases)
    ]
