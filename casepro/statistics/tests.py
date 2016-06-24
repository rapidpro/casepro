from __future__ import unicode_literals

import pytz

from datetime import date, datetime

from casepro.test import BaseCasesTest

from .models import DailyOrgCount, DailyPartnerCount, DailyUserCount


class DailyCountsTest(BaseCasesTest):
    def test_counts(self):
        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        ned = self.create_contact(self.nyaruka, 'C-002', "Ned")

        tz = pytz.timezone("Africa/Kigali")

        self.create_outgoing(self.unicef, self.admin, 201, 'C', "Hello", ann,
                             created_on=datetime(2015, 1, 1, 9, 0, tzinfo=tz))  # admin on Jan 1st
        self.create_outgoing(self.unicef, self.admin, 202, 'B', "Hello", ann,
                             created_on=datetime(2015, 1, 1, 10, 0, tzinfo=tz))  # admin on Jan 1st
        self.create_outgoing(self.unicef, self.admin, 203, 'F', "Hello", ann,
                             created_on=datetime(2015, 1, 1, 11, 0, tzinfo=tz))  # admin on Jan 1st (not a reply)
        self.create_outgoing(self.unicef, self.user1, 204, 'C', "Hello", ann,
                             created_on=datetime(2015, 1, 1, 12, 0, tzinfo=tz))  # user #1 on Jan 1st
        self.create_outgoing(self.unicef, self.user1, 205, 'C', "Hello", ann,
                             created_on=datetime(2015, 1, 2, 9, 0, tzinfo=tz))  # user #1 on Jan 2nd
        self.create_outgoing(self.unicef, self.user1, 206, 'C', "Hello", ann,
                             created_on=datetime(2015, 1, 2, 9, 0, tzinfo=tz))  # user #1 on Jan 2nd
        self.create_outgoing(self.unicef, self.user2, 207, 'C', "Hello", ann,
                             created_on=datetime(2015, 1, 2, 9, 0, tzinfo=tz))  # user #2 on Jan 2nd
        self.create_outgoing(self.unicef, self.user3, 208, 'C', "Hello", ann,
                             created_on=datetime(2015, 1, 3, 9, 0, tzinfo=tz))  # user #3 on Jan 3rd
        self.create_outgoing(self.nyaruka, self.user4, 209, 'C', "Hello", ned,
                             created_on=datetime(2015, 1, 3, 9, 0, tzinfo=tz))  # user #4 on Jan 3rd (other org)

        # check overall totals
        self.assertEqual(DailyOrgCount.get_total(self.unicef, DailyOrgCount.TYPE_REPLIES), 7)
        self.assertEqual(DailyPartnerCount.get_total(self.moh, DailyPartnerCount.TYPE_REPLIES), 4)
        self.assertEqual(DailyPartnerCount.get_total(self.who, DailyPartnerCount.TYPE_REPLIES), 1)
        self.assertEqual(DailyUserCount.get_total(self.unicef, self.admin, 'R'), 2)
        self.assertEqual(DailyUserCount.get_total(self.unicef, self.user1, 'R'), 3)

        # check daily totals
        self.assertEqual(DailyOrgCount.get_daily_totals(self.unicef, DailyOrgCount.TYPE_REPLIES), [
            (date(2015, 1, 1), 3), (date(2015, 1, 2), 3), (date(2015, 1, 3), 1)
        ])
        self.assertEqual(DailyPartnerCount.get_daily_totals(self.moh, DailyOrgCount.TYPE_REPLIES), [
            (date(2015, 1, 1), 1), (date(2015, 1, 2), 3)
        ])
        self.assertEqual(DailyUserCount.get_daily_totals(self.unicef, self.user1, DailyOrgCount.TYPE_REPLIES), [
            (date(2015, 1, 1), 1), (date(2015, 1, 2), 2)
        ])

        counts = DailyPartnerCount.get_totals(self.unicef.partners.all(), DailyPartnerCount.TYPE_REPLIES,
                                              since=None, until=None)
        self.assertEqual(counts, {self.moh: 4, self.who: 1})

        counts = DailyUserCount.get_totals(self.unicef, self.unicef.get_users(), DailyUserCount.TYPE_REPLIES,
                                           since=None, until=None)
        self.assertEqual(counts, {self.admin: 2, self.user1: 3, self.user2: 1, self.user3: 1})

        DailyOrgCount.squash()
        DailyPartnerCount.squash()
        DailyUserCount.squash()

        self.assertEqual(DailyOrgCount.objects.count(), 4)
        self.assertEqual(DailyOrgCount.objects.filter(squashed=False).count(), 0)
        self.assertEqual(DailyOrgCount.objects.get(org=self.unicef, day=date(2015, 1, 1)).count, 3)
        self.assertEqual(DailyOrgCount.objects.get(org=self.unicef, day=date(2015, 1, 2)).count, 3)
        self.assertEqual(DailyOrgCount.objects.get(org=self.unicef, day=date(2015, 1, 3)).count, 1)
        self.assertEqual(DailyOrgCount.objects.get(org=self.nyaruka, day=date(2015, 1, 3)).count, 1)

        self.assertEqual(DailyPartnerCount.objects.count(), 4)
        self.assertEqual(DailyPartnerCount.objects.filter(squashed=False).count(), 0)
        self.assertEqual(DailyPartnerCount.objects.get(partner=self.moh, day=date(2015, 1, 1)).count, 1)
        self.assertEqual(DailyPartnerCount.objects.get(partner=self.moh, day=date(2015, 1, 2)).count, 3)
        self.assertEqual(DailyPartnerCount.objects.get(partner=self.who, day=date(2015, 1, 3)).count, 1)
        self.assertEqual(DailyPartnerCount.objects.get(partner=self.klab, day=date(2015, 1, 3)).count, 1)

        self.assertEqual(DailyUserCount.objects.count(), 6)
        self.assertEqual(DailyUserCount.objects.filter(squashed=False).count(), 0)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.admin, day=date(2015, 1, 1)).count, 2)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.user1, day=date(2015, 1, 1)).count, 1)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.user1, day=date(2015, 1, 2)).count, 2)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.user2, day=date(2015, 1, 2)).count, 1)
        self.assertEqual(DailyUserCount.objects.get(org=self.unicef, user=self.user3, day=date(2015, 1, 3)).count, 1)
        self.assertEqual(DailyUserCount.objects.get(org=self.nyaruka, user=self.user4, day=date(2015, 1, 3)).count, 1)

        self.create_outgoing(self.unicef, self.admin, 210, 'C', "Hello", ann,
                             created_on=datetime(2015, 1, 3, 10, 0, tzinfo=tz))  # admin on Jan 3rd
        self.create_outgoing(self.unicef, self.user1, 211, 'C', "Hello", ann,
                             created_on=datetime(2015, 1, 1, 12, 0, tzinfo=tz))  # user #1 on Jan 1st
