# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import six

from collections import defaultdict, Counter
from django.db import migrations


def populate_outgoing_counts(apps, schema_editor):
    Org = apps.get_model('orgs', 'Org')
    Outgoing = apps.get_model('msgs', 'Outgoing')
    OutgoingCount = apps.get_model('msgs', 'OutgoingCount')

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
            OutgoingCount.objects.create(type='O', org=org, day=day, count=org_count)

            # record day counts for each partner
            partner_counts = Counter([r['partner'] for r in day_replies])
            for partner_id, count in six.iteritems(partner_counts):
                OutgoingCount.objects.create(type='P', org=org, partner_id=partner_id, day=day, count=count)

            # record day counts for each partner/user pairing
            user_counts = Counter([(r['partner'], r['created_by']) for r in day_replies])
            for (partner_id, user_id), count in six.iteritems(user_counts):
                OutgoingCount.objects.create(type='U', org=org, partner_id=partner_id, user_id=user_id, day=day, count=count)

        print("Created reply counts for org %s [%d] with %d replies" % (org.name, org.pk, len(replies)))


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0050_outgoingcount'),
    ]

    operations = [
        migrations.RunPython(populate_outgoing_counts)
    ]
