from collections import defaultdict

from dash.utils import chunks
from django.db import migrations


def populate_incoming_counts(apps, schema_editor):
    Org = apps.get_model("orgs", "Org")
    Message = apps.get_model("msgs", "Message")
    DailyCount = apps.get_model("statistics", "DailyCount")

    for org in Org.objects.all():
        print("Populating incoming counts for %s [%d]..." % (org.name, org.pk))

        message_ids = list(org.incoming_messages.values_list("pk", flat=True))

        print(" > Fetched ids of all %d org messages" % len(message_ids))

        num_processed = 0

        for id_batch in chunks(message_ids, 5000):
            # extract this batch of messages with day and labels
            messages = Message.objects.filter(pk__in=id_batch).prefetch_related("labels")
            messages = list(messages.extra(select={"day": "DATE(created_on)"}))

            # organize into lists by day
            messages_by_day = defaultdict(list)
            for message in messages:
                messages_by_day[message.day].append(message)

            # process each day's messages
            for day in sorted(messages_by_day.keys()):
                day_messages = messages_by_day[day]

                # record day count for org
                org_count = len(day_messages)
                DailyCount.objects.create(day=day, item_type="I", scope="org:%d" % org.pk, count=org_count)

                # count labels for this day
                label_counts = defaultdict(int)
                for message in day_messages:
                    for label in message.labels.all():
                        label_counts[label] += 1

                # record day count for labels
                for label, label_count in label_counts.items():
                    DailyCount.objects.create(day=day, item_type="I", scope="label:%d" % label.pk, count=label_count)

            num_processed += len(id_batch)
            print("Processed %d of %d messages" % (num_processed, len(message_ids)))


class Migration(migrations.Migration):

    dependencies = [("statistics", "0003_auto_20160701_1412")]

    operations = [migrations.RunPython(populate_incoming_counts)]
