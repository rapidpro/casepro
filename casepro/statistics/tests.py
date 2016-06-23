from __future__ import unicode_literals

from casepro.test import BaseCasesTest

from .models import DailyOrgCount, DailyPartnerCount, DailyOrgUserCount


class DailyCountsTest(BaseCasesTest):
    def test_counts(self):
        ann = self.create_contact(self.unicef, 'C-001', "Ann")
        ned = self.create_contact(self.nyaruka, 'C-002', "Ned")

        self.create_outgoing(self.unicef, self.admin, 201, 'C', "Hello", ann)
        self.create_outgoing(self.unicef, self.admin, 202, 'B', "Hello", ann)
        self.create_outgoing(self.unicef, self.admin, 203, 'F', "Hello", ann)  # not a reply
        self.create_outgoing(self.unicef, self.user1, 204, 'C', "Hello", ann)
        self.create_outgoing(self.unicef, self.user1, 205, 'C', "Hello", ann)
        self.create_outgoing(self.unicef, self.user1, 206, 'C', "Hello", ann)
        self.create_outgoing(self.unicef, self.user2, 207, 'C', "Hello", ann)
        self.create_outgoing(self.unicef, self.user3, 208, 'C', "Hello", ann)
        self.create_outgoing(self.nyaruka, self.user4, 209, 'C', "Hello", ned)  # other org

        self.assertEqual(DailyOrgCount.get_total(self.unicef, DailyOrgCount.TYPE_REPLIES), 7)
        self.assertEqual(DailyPartnerCount.get_total(self.moh, DailyPartnerCount.TYPE_REPLIES), 4)
        self.assertEqual(DailyPartnerCount.get_total(self.who, DailyPartnerCount.TYPE_REPLIES), 1)
        self.assertEqual(DailyOrgUserCount.get_total(self.unicef, self.admin, 'R'), 2)
        self.assertEqual(DailyOrgUserCount.get_total(self.unicef, self.user1, 'R'), 3)

        counts = DailyPartnerCount.get_totals(self.unicef.partners.all(), DailyPartnerCount.TYPE_REPLIES,
                                              since=None, until=None)
        self.assertEqual(counts, {self.moh: 4, self.who: 1})

        counts = DailyOrgUserCount.get_totals(self.unicef, self.unicef.get_users(), DailyOrgUserCount.TYPE_REPLIES,
                                              since=None, until=None)
        self.assertEqual(counts, {self.admin: 2, self.user1: 3, self.user2: 1, self.user3: 1})
