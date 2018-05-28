# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def calculate_totals_for_cases(apps, schema_editor):
    from casepro.statistics.models import datetime_to_date

    Case = apps.get_model("cases", "Case")
    CaseAction = apps.get_model("cases", "CaseAction")
    DailyCount = apps.get_model("statistics", "DailyCount")

    cases = list(Case.objects.all().order_by("id"))
    num_updated = 0

    for case in cases:
        open_action = case.actions.filter(action="O").first()
        org = open_action.case.org
        user = open_action.created_by
        partner = open_action.case.assignee
        case = open_action.case

        day = datetime_to_date(open_action.created_on, org)
        DailyCount.objects.create(day=day, item_type="C", scope="org:%d" % org.pk, count=1)
        DailyCount.objects.create(day=day, item_type="C", scope="org:%d:user:%d" % (org.pk, user.pk), count=1)
        DailyCount.objects.create(day=day, item_type="C", scope="partner:%d" % partner.pk, count=1)

        try:
            # only check the first close action, don't count reopens
            close_action = case.actions.filter(action="C").earliest("created_on")
            DailyCount.objects.create(day=day, item_type="D", scope="org:%d" % close_action.case.org.pk, count=1)
            DailyCount.objects.create(
                day=day,
                item_type="D",
                scope="org:%d:user:%d" % (close_action.case.org.pk, close_action.created_by.pk),
                count=1,
            )
            DailyCount.objects.create(
                day=day, item_type="D", scope="partner:%d" % close_action.case.assignee.pk, count=1
            )

            num_updated += 1
            if num_updated % 100 == 0:
                print("Created daily counts for %d of %d cases" % (num_updated, len(cases)))

        except CaseAction.DoesNotExist:
            # no close action means to close totals to count for this case
            pass


def remove_totals_for_cases(apps, schema_editor):
    DailyCount = apps.get_model("statistics", "DailyCount")
    db_alias = schema_editor.connection.alias
    DailyCount.objects.using(db_alias).filter(item_type="D").delete()
    DailyCount.objects.using(db_alias).filter(item_type="C").delete()


class Migration(migrations.Migration):

    dependencies = [("statistics", "0007_populate_label_totals"), ("cases", "0042_auto_20160805_1003")]

    operations = [
        # migrations.RunPython(calculate_totals_for_cases, remove_totals_for_cases),
        # the reverse migration is commented out because it could remove data created after this migration was run,
        # so it should only be used when you know it will do what you want it to do
        migrations.RunPython(calculate_totals_for_cases)
    ]
