# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import six

from collections import defaultdict, Counter
from django.db import migrations


def populate_reply_counts(apps, schema_editor):
    Org = apps.get_model('orgs', 'Org')
    Outgoing = apps.get_model('msgs', 'Outgoing')
    DailyCount = apps.get_model('statistics', 'DailyCount')

    for org in Org.objects.all():
        # extract all of this orgs replies as dicts of day, partner id and user id
        replies = Outgoing.objects.filter(org=org, activity__in=('C', 'B'))
        replies = list(replies.extra(select={'day': 'DATE(created_on)'}).values('day', 'partner', 'created_by'))

        # organize into lists by day
        replies_by_day = defaultdict(list)
        for reply in replies:
            replies_by_day[reply['day']].append(reply)

        # process each day's replies
        for day in sorted(replies_by_day.keys()):
            day_replies = replies_by_day[day]

            # record day count for org
            org_count = len(day_replies)
            DailyCount.objects.create(day=day, item_type='R', scope='org:%d' % org.pk, count=org_count)

            # record day counts for each partner
            partner_counts = Counter([r['partner'] for r in day_replies if r['partner']])
            for partner_id, count in six.iteritems(partner_counts):
                DailyCount.objects.create(day=day, item_type='R', scope='partner:%d' % partner_id, count=count)

            # record day counts for each org/user
            user_counts = Counter([r['created_by'] for r in day_replies])
            for user_id, count in six.iteritems(user_counts):
                DailyCount.objects.create(day=day, item_type='R', scope='org:%d:user:%d' % (org.pk, user_id), count=count)

        print("Created reply counts for org %s [%d] with %d replies" % (org.name, org.pk, len(replies)))


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0001_initial'),
        ('msgs', '0047_outgoing_urn'),
    ]

    operations = [
        migrations.RunPython(populate_reply_counts)
    ]
