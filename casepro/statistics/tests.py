from __future__ import unicode_literals

import pytz
import random

from dash.orgs.models import Org
from datetime import date, datetime, time
from django.core.urlresolvers import reverse
from django.utils import timezone
from mock import patch

from casepro.test import BaseCasesTest

from .models import DailyCount
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

        def check_counts():
            # check overall totals
            self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').total(), 12)
            self.assertEqual(DailyCount.get_by_partner([self.moh], 'R').total(), 4)
            self.assertEqual(DailyCount.get_by_partner([self.who], 'R').total(), 6)
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.admin], 'R').total(), 2)
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.user1], 'R').total(), 3)
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.user2], 'R').total(), 1)
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.user3], 'R').total(), 6)
            self.assertEqual(DailyCount.get_by_user(self.nyaruka, [self.user4], 'R').total(), 1)

            # check daily totals
            self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').day_totals(), [
                (date(2015, 1, 1), 3), (date(2015, 1, 2), 3), (date(2015, 1, 3), 1),
                (date(2015, 2, 1), 1), (date(2015, 2, 2), 2), (date(2015, 2, 28), 1), (date(2015, 3, 1), 1)
            ])
            self.assertEqual(DailyCount.get_by_partner([self.moh], 'R').day_totals(), [
                (date(2015, 1, 1), 1), (date(2015, 1, 2), 3)
            ])
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.user1], 'R').day_totals(), [
                (date(2015, 1, 1), 1), (date(2015, 1, 2), 2)
            ])

            # check monthly totals
            self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').month_totals(), [
                (1, 7), (2, 4), (3, 1)
            ])
            self.assertEqual(DailyCount.get_by_partner([self.moh], 'R').month_totals(), [
                (1, 4)
            ])
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.admin], 'R').month_totals(), [
                (1, 2)
            ])

            # check org totals
            self.assertEqual(DailyCount.get_by_org(Org.objects.all(), 'R').scope_totals(), {
                self.unicef: 12, self.nyaruka: 1
            })

            # check partner totals
            self.assertEqual(DailyCount.get_by_partner(self.unicef.partners.all(), 'R').scope_totals(), {
                self.moh: 4, self.who: 6
            })

            # check user totals
            self.assertEqual(DailyCount.get_by_user(self.unicef, self.unicef.get_users(), 'R').scope_totals(), {
                self.admin: 2, self.user1: 3, self.user2: 1, self.user3: 6
            })

        check_counts()
        self.assertEqual(DailyCount.objects.count(), 37)

        # squash all daily counts
        squash_counts()

        check_counts()
        self.assertEqual(DailyCount.objects.count(), 26)

        # add new count on day that already has a squashed value
        self.send_outgoing(self.admin, date(2015, 1, 1))

        self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').total(), 13)

        # squash all daily counts again
        squash_counts()

        self.assertEqual(DailyCount.objects.count(), 26)
        self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').total(), 13)

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
