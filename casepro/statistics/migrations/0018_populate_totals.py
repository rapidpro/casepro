# Generated by Django 2.2.18 on 2021-03-10 16:18

from django.db import migrations, transaction
from django.db.models import Sum

TYPE_REPLIES = "R"
TYPE_CASE_OPENED = "C"
TYPE_CASE_CLOSED = "D"


def populate(DailyCount, TotalCount):
    for item_type in (TYPE_REPLIES, TYPE_CASE_OPENED, TYPE_CASE_CLOSED):
        print(f"Populating total counts for item type {item_type}")

        populate_for_item_type(DailyCount, TotalCount, item_type)


def populate_for_item_type(DailyCount, TotalCount, item_type):
    scopes = list(DailyCount.objects.filter(item_type=item_type).values_list("scope", flat=True).distinct("scope"))

    print(f" > found distinct {len(scopes)} scopes")

    for scope in scopes:
        total = DailyCount.objects.filter(item_type=item_type, scope=scope).aggregate(total=Sum("count"))
        total = total["total"] if total["total"] is not None else 0

        with transaction.atomic():
            TotalCount.objects.filter(item_type=item_type, scope=scope).delete()
            TotalCount.objects.create(item_type=item_type, scope=scope, is_squashed=True, count=total)

        print(f" > populated total count ({total}) for item type {item_type} in scope {scope}")


def populate_totals(apps, schema_editor):
    DailyCount = apps.get_model("statistics", "DailyCount")  # noqa
    TotalCount = apps.get_model("statistics", "TotalCount")  # noqa

    populate(DailyCount, TotalCount)


def reverse(apps, schema_editor):
    pass


def apply_manual():
    from casepro.statistics.models import DailyCount, TotalCount

    populate(DailyCount, TotalCount)


class Migration(migrations.Migration):

    dependencies = [
        ("statistics", "0017_auto_20191216_1457"),
    ]

    operations = [migrations.RunPython(populate_totals, reverse)]
