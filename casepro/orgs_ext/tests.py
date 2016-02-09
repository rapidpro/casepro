from __future__ import absolute_import, unicode_literals

from casepro.contacts.models import Field, Group
from casepro.test import BaseCasesTest
from django.core.urlresolvers import reverse


class OrgExtCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(OrgExtCRUDLTest, self).setUp()

        self.state = Field.create(self.unicef, 'state', "State")
        self.age = Field.create(self.unicef, 'age', "Age")
        self.reporters = Group.create(self.unicef, 'G-001', "U-Reporters")
        self.optedout = Group.create(self.unicef, 'G-002', "Opted Out")

        self.unicef.set_banner_text("Howdy (U)Partner!")
        self.unicef.set_contact_fields([self.age.key])
        self.unicef.set_suspend_groups([self.reporters.uuid])

    def test_home(self):
        url = reverse('orgs_ext.org_home')

        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Kidus (kidus@unicef.org)")

    def test_edit(self):
        url = reverse('orgs_ext.org_edit')

        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        form_fields = response.context['form'].fields

        self.assertEqual(form_fields['banner_text'].initial, "Howdy (U)Partner!")
        self.assertEqual(form_fields['contact_fields'].choices,
                         [('age', "Age (age)"), ('state', "State (state)")])
        self.assertEqual(form_fields['contact_fields'].initial, ['age'])
        self.assertEqual(form_fields['suspend_groups'].choices,
                         [(self.optedout.uuid, "Opted Out"), (self.reporters.uuid, "U-Reporters")])
        self.assertEqual(form_fields['suspend_groups'].initial, [self.reporters.uuid])

