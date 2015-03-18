from __future__ import absolute_import, unicode_literals

from upartners.partners.models import Partner
from upartners.profiles import ROLE_ANALYST, ROLE_MANAGER
from upartners.test import UPartnersTest


class PartnerTest(UPartnersTest):
    def test_create(self):
        wfp = Partner.create(self.unicef, "WFP")
        self.assertEqual(wfp.org, self.unicef)
        self.assertEqual(wfp.name, "WFP")
        self.assertEqual(unicode(wfp), "WFP")

        # create some users for this partner
        jim = self.create_user(self.unicef, wfp, ROLE_MANAGER, "Jim", "jim@wfp.org")
        kim = self.create_user(self.unicef, wfp, ROLE_ANALYST, "Kim", "kim@wfp.org")

        self.assertEqual(set(wfp.get_users()), {jim, kim})
        self.assertEqual(set(wfp.get_managers()), {jim})
        self.assertEqual(set(wfp.get_analysts()), {kim})

        # give this partner access to the AIDS and Code labels
        self.aids.partners.add(wfp)
        self.code.partners.add(wfp)

        self.assertEqual(set(wfp.get_labels()), {self.aids, self.code})
