from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse
from casepro.test import BaseCasesTest
from mock import patch
from .models import TaskState
from .tasks import org_task


def test_over_time_window(org, started_on, prev_started_on):
    """The org task function below will be transformed by @org_task decorator, so easier to mock this"""
    return {}


@org_task('test-task')
def test_org_task(org, started_on, prev_started_on):
    return test_over_time_window(org, started_on, prev_started_on)


class OrgTaskTest(BaseCasesTest):
    @patch('casepro.orgs_ext.tests.test_over_time_window')
    def test_decorator(self, mock_over_time_window):
        mock_over_time_window.return_value = {'foo': "bar", 'zed': 123}

        # org tasks are invoked with a single org id
        test_org_task(self.unicef.pk)

        # should now have task state for that org
        state1 = TaskState.objects.get(org=self.unicef, task_key='test-task')

        self.assertIsNotNone(state1.started_on)
        self.assertIsNotNone(state1.ended_on)
        self.assertEqual(state1.last_successfully_started_on, state1.started_on)
        self.assertFalse(state1.is_running())
        self.assertEqual(state1.get_last_results(), {'foo': "bar", 'zed': 123})
        self.assertEqual(state1.get_time_taken(), (state1.ended_on - state1.started_on).total_seconds())
        self.assertFalse(state1.is_failing)

        self.assertEqual(list(TaskState.get_failing()), [])

        mock_over_time_window.assert_called_once_with(self.unicef, None, state1.started_on)
        mock_over_time_window.reset_mock()

        # running again will update state
        test_org_task(self.unicef.pk)
        state2 = TaskState.objects.get(org=self.unicef, task_key='test-task')

        self.assertGreater(state2.started_on, state1.started_on)
        self.assertEqual(state2.last_successfully_started_on, state2.started_on)

        mock_over_time_window.assert_called_once_with(self.unicef, state1.started_on, state2.started_on)
        mock_over_time_window.reset_mock()

        mock_over_time_window.side_effect = ValueError("DOH!")

        # test when task throw exception
        self.assertRaises(ValueError, test_org_task, self.unicef.pk)

        state3 = TaskState.objects.get(org=self.unicef, task_key='test-task')

        self.assertGreater(state3.started_on, state2.started_on)
        self.assertGreater(state3.ended_on, state2.ended_on)
        self.assertEqual(state3.last_successfully_started_on, state2.started_on)  # hasn't changed
        self.assertFalse(state3.is_running())
        self.assertEqual(state3.get_last_results(), None)
        self.assertTrue(state3.is_failing)

        self.assertEqual(list(TaskState.get_failing()), [state3])

        mock_over_time_window.assert_called_once_with(self.unicef, state2.started_on, state3.started_on)
        mock_over_time_window.reset_mock()

        # test when called, again, start time is from last successful run
        self.assertRaises(ValueError, test_org_task, self.unicef.pk)

        state4 = TaskState.objects.get(org=self.unicef, task_key='test-task')

        self.assertGreater(state4.started_on, state3.started_on)
        self.assertGreater(state4.ended_on, state3.ended_on)
        self.assertEqual(state4.last_successfully_started_on, state2.started_on)

        mock_over_time_window.assert_called_once_with(self.unicef, state2.started_on, state4.started_on)
        mock_over_time_window.reset_mock()


class OrgExtCRUDLTest(BaseCasesTest):
    def test_home(self):
        url = reverse('orgs_ext.org_home')

        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Kidus (kidus@unicef.org)")
