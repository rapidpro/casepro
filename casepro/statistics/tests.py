from __future__ import unicode_literals

import pytz
import random

from datetime import date, datetime, time
from django.core.urlresolvers import reverse
from django.utils import timezone
from mock import patch

from casepro.test import BaseCasesTest

from .models import DailyOrgCount, DailyPartnerCount, DailyUserCount
from .tasks import squash_counts


class DailyCountsTest(BaseCasesTest):
    def setUp(self):
        super(DailyCountsTest, self).setUp()

        self.ann = self.create_contact(self.unicef, 'C-001', "Ann")
        self.ned = self.create_contact(self.nyaruka, 'C-002', "Ned")

        self._backend_id = 200

    def send_outgoing(self, user, day, count=1):
        for m in range(count):
            self._backend_id += 1
            hour = random.randrange(0, 24)
            minute = random.randrange(0, 60)
            created_on = pytz.timezone("Africa/Kampala").localize(datetime.combine(day, time(hour, minute, 0, 0)))

            self.create_outgoing(self.unicef, user, self._backend_id, 'B', "Hello", self.ann, created_on=created_on)

    def test_counts(self):
        self.send_outgoing(self.admin, date(2015, 1, 1), count=2)
        self.send_outgoing(self.user1, date(2015, 1, 1))
        self.send_outgoing(self.user1, date(2015, 1, 2), count=2)
        self.send_outgoing(self.user2, date(2015, 1, 2))
        self.send_outgoing(self.user3, date(2015, 1, 3))
        self.send_outgoing(self.user3, date(2015, 2, 1))
        self.send_outgoing(self.user3, date(2015, 2, 2), count=2)
        self.send_outgoing(self.user3, date(2015, 2, 28))
        self.send_outgoing(self.user3, date(2015, 3, 1))

        self.create_outgoing(self.unicef, self.admin, 203, 'F', "Hello", self.ann,
                             created_on=datetime(2015, 1, 1, 11, 0, tzinfo=pytz.UTC))  # admin on Jan 1st (not a reply)
        self.create_outgoing(self.nyaruka, self.user4, 209, 'C', "Hello", self.ned,
                             created_on=datetime(2015, 1, 3, 9, 0, tzinfo=pytz.UTC))  # user #4 on Jan 3rd (other org)

        # check overall totals
        self.assertEqual(DailyOrgCount.get_total(self.unicef, 'R'), 12)
        self.assertEqual(DailyPartnerCount.get_total(self.moh, 'R'), 4)
        self.assertEqual(DailyPartnerCount.get_total(self.who, 'R'), 6)
        self.assertEqual(DailyUserCount.get_total(self.unicef, self.admin, 'R'), 2)
        self.assertEqual(DailyUserCount.get_total(self.unicef, self.user1, 'R'), 3)
        self.assertEqual(DailyUserCount.get_total(self.unicef, self.user2, 'R'), 1)
        self.assertEqual(DailyUserCount.get_total(self.unicef, self.user3, 'R'), 6)
        self.assertEqual(DailyUserCount.get_total(self.nyaruka, self.user4, 'R'), 1)

        # check daily totals
        self.assertEqual(DailyOrgCount.get_daily_totals(self.unicef, DailyOrgCount.TYPE_REPLIES), [
            (date(2015, 1, 1), 3), (date(2015, 1, 2), 3), (date(2015, 1, 3), 1),
            (date(2015, 2, 1), 1), (date(2015, 2, 2), 2), (date(2015, 2, 28), 1), (date(2015, 3, 1), 1)
        ])
        self.assertEqual(DailyPartnerCount.get_daily_totals(self.moh, DailyOrgCount.TYPE_REPLIES), [
            (date(2015, 1, 1), 1), (date(2015, 1, 2), 3)
        ])
        self.assertEqual(DailyUserCount.get_daily_totals(self.unicef, self.user1, DailyOrgCount.TYPE_REPLIES), [
            (date(2015, 1, 1), 1), (date(2015, 1, 2), 2)
        ])

        # check monthly totals
        self.assertEqual(DailyOrgCount.get_monthly_totals(self.unicef, DailyOrgCount.TYPE_REPLIES), [
            (1, 7), (2, 4), (3, 1)
        ])
        # check monthly totals
        self.assertEqual(DailyPartnerCount.get_monthly_totals(self.moh, DailyOrgCount.TYPE_REPLIES), [
            (1, 4)
        ])
        # check monthly totals
        self.assertEqual(DailyUserCount.get_monthly_totals(self.unicef, self.admin, DailyOrgCount.TYPE_REPLIES), [
            (1, 2)
        ])

        counts = DailyPartnerCount.get_totals(self.unicef.partners.all(), DailyPartnerCount.TYPE_REPLIES,
                                              since=None, until=None)
        self.assertEqual(counts, {self.moh: 4, self.who: 6})

        counts = DailyUserCount.get_totals(self.unicef, self.unicef.get_users(), DailyUserCount.TYPE_REPLIES,
                                           since=None, until=None)
        self.assertEqual(counts, {self.admin: 2, self.user1: 3, self.user2: 1, self.user3: 6})

        # squash all daily counts
        squash_counts()

        self.assertEqual(DailyOrgCount.objects.count(), 8)
        self.assertEqual(DailyOrgCount.objects.filter(squashed=False).count(), 0)
        self.assertEqual(DailyOrgCount.objects.get(org=self.unicef, day=date(2015, 1, 1)).count, 3)
        self.assertEqual(DailyOrgCount.objects.get(org=self.unicef, day=date(2015, 1, 2)).count, 3)
        self.assertEqual(DailyOrgCount.objects.get(org=self.unicef, day=date(2015, 1, 3)).count, 1)
        self.assertEqual(DailyOrgCount.objects.get(org=self.nyaruka, day=date(2015, 1, 3)).count, 1)

        self.assertEqual(DailyPartnerCount.objects.count(), 8)
        self.assertEqual(DailyPartnerCount.objects.filter(squashed=False).count(), 0)
        self.assertEqual(DailyPartnerCount.objects.get(partner=self.moh, day=date(2015, 1, 1)).count, 1)
        self.assertEqual(DailyPartnerCount.objects.get(partner=self.moh, day=date(2015, 1, 2)).count, 3)
        self.assertEqual(DailyPartnerCount.objects.get(partner=self.who, day=date(2015, 1, 3)).count, 1)
        self.assertEqual(DailyPartnerCount.objects.get(partner=self.klab, day=date(2015, 1, 3)).count, 1)

        self.assertEqual(DailyUserCount.objects.count(), 10)
        self.assertEqual(DailyUserCount.objects.filter(squashed=False).count(), 0)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.admin, day=date(2015, 1, 1)).count, 2)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.user1, day=date(2015, 1, 1)).count, 1)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.user1, day=date(2015, 1, 2)).count, 2)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.user2, day=date(2015, 1, 2)).count, 1)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.user3, day=date(2015, 1, 3)).count, 1)
        self.assertEqual(DailyUserCount.objects.get(org=self.nyaruka, user=self.user4, day=date(2015, 1, 3)).count, 1)

        # add new count on day that already has a squashed value
        self.send_outgoing(self.admin, date(2015, 3, 1))

        self.assertEqual(DailyOrgCount.get_total(self.unicef, 'R'), 13)

        # squash all daily counts
        squash_counts()

        self.assertEqual(DailyOrgCount.objects.count(), 8)
        self.assertEqual(DailyOrgCount.objects.filter(squashed=False).count(), 0)
        self.assertEqual(DailyOrgCount.get_total(self.unicef, 'R'), 13)

    def test_replies_chart(self):
        url = reverse('stats.partner_replies_chart', args=[self.moh.pk])

        self.login(self.user3)  # even users from other partners can see this

        self.send_outgoing(self.user1, date(2016, 1, 15))  # Jan 15th
        self.send_outgoing(self.user1, date(2016, 1, 20))  # Jan 20th
        self.send_outgoing(self.user1, date(2016, 2, 1))  # Feb 1st
        self.send_outgoing(self.user3, date(2016, 2, 1))  # different partner

        # simulate making request in April
        with patch.object(timezone, 'now', return_value=datetime(2016, 4, 20, 9, 0, tzinfo=pytz.UTC)):
            response = self.url_get('unicef', url)

        self.assertEqual(response.json, {
            'categories': ["November", "December", "January", "February", "March", "April"],
            'series': [0, 0, 2, 1, 0, 0]
        })
