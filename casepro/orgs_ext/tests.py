from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse
from casepro.test import BaseCasesTest
from .models import scheduled_org_task, OrgTaskState


@scheduled_org_task('test-task')
def test_org_task(org, running_on, last_run_on):
    return {'foo': "bar", 'zed': org.name}


class OrgTaskTest(BaseCasesTest):
    def test_decorator(self):
        test_org_task()

        # should now have task states for both orgs
        org1_state = OrgTaskState.objects.get(org=self.unicef, task_key='test-task')
        org2_state = OrgTaskState.objects.get(org=self.nyaruka, task_key='test-task')

        self.assertEqual(org1_state.last_results, {'foo': "bar", 'zed': "UNICEF"})
        self.assertIsNotNone(org1_state.last_run_on)
        self.assertEqual(org2_state.last_results, {'foo': "bar", 'zed': "Nyaruka"})
        self.assertIsNotNone(org2_state.last_run_on)

        test_org_task()
        test_org_task()


class OrgExtCRUDLTest(BaseCasesTest):
    def test_home(self):
        url = reverse('orgs_ext.org_home')

        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Kidus (kidus@unicef.org)")
