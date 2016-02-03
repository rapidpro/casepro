from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse
from casepro.test import BaseCasesTest
from .models import TaskState
from .tasks import org_task


ERROR_ON_TEST_TASK = False


@org_task('test-task')
def test_org_task(org, started_on, prev_started_on):
    if ERROR_ON_TEST_TASK:
        raise ValueError("Doh!")
    else:
        return {'foo': "bar", 'zed': org.name}


class OrgTaskTest(BaseCasesTest):
    def test_decorator(self):
        global ERROR_ON_TEST_TASK
        ERROR_ON_TEST_TASK = False

        # org tasks are invoked with a single org id
        test_org_task(self.unicef.pk)

        # should now have task state for that org
        org_state = TaskState.objects.get(org=self.unicef, task_key='test-task')

        self.assertIsNotNone(org_state.started_on)
        self.assertIsNotNone(org_state.ended_on)
        self.assertFalse(org_state.is_running())
        self.assertEqual(org_state.get_last_results(), {'foo': "bar", 'zed': "UNICEF"})
        self.assertEqual(org_state.get_time_taken(), (org_state.ended_on - org_state.started_on).total_seconds())
        self.assertFalse(org_state.is_failing)

        old_started_on = org_state.started_on

        # running again will update state
        test_org_task(self.unicef.pk)
        org_state = TaskState.objects.get(org=self.unicef, task_key='test-task')

        self.assertGreater(org_state.started_on, old_started_on)

        self.assertEqual(list(TaskState.get_failing()), [])

        ERROR_ON_TEST_TASK = True

        # test when task fails
        test_org_task(self.unicef.pk)
        org_state = TaskState.objects.get(org=self.unicef, task_key='test-task')

        self.assertIsNotNone(org_state.started_on)
        self.assertIsNotNone(org_state.ended_on)
        self.assertFalse(org_state.is_running())
        self.assertEqual(org_state.get_last_results(), None)
        self.assertTrue(org_state.is_failing)

        self.assertEqual(list(TaskState.get_failing()), [org_state])


class OrgExtCRUDLTest(BaseCasesTest):
    def test_home(self):
        url = reverse('orgs_ext.org_home')

        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Kidus (kidus@unicef.org)")
