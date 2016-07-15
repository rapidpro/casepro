from django.core.urlresolvers import reverse
from django.test import modify_settings

from casepro.test import BaseCasesTest


@modify_settings(INSTALLED_APPS={
    'append': 'casepro.pods.PodPlugin',
})
class ViewPodDataView(BaseCasesTest):
    '''
    Tests relating to the view_pod_data view.
    '''
    def test_invalid_method(self):
        '''
        If the request method is not GET, an appropriate error should be
        returned.
        '''
        response = self.url_post(
            'unicef', reverse('read_pod_data', args=('0',)))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json, {
            'reason': 'Method not allowed'}
        )

    def test_pod_doesnt_exist(self):
        '''
        If the requested pod id is invalid, an appropriate 404 error should be
        returned.
        '''
        with self.settings(PODS=[]):
            from casepro.pods import registry
            reload(registry)
        response = self.url_get(
            'unicef', reverse('read_pod_data', args=('0',)))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {
            'reason': 'Pod does not exist'}
        )

    def test_pod_valid_request(self):
        '''
        If it is a valid get request, the data from the pod should be returned.
        '''
        with self.settings(PODS=[{'label': 'base_pod'}]):
            from casepro.pods import registry
            reload(registry)
        response = self.url_get(
            'unicef', reverse('read_pod_data', args=('0',)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {})


@modify_settings(INSTALLED_APPS={
    'append': 'casepro.pods.PodPlugin',
})
class PerformPodActionView(BaseCasesTest):
    '''
    Tests relating to the perform_pod_action view.
    '''
    def test_invalid_method(self):
        '''
        If the request method is not POST, an appropriate error should be
        returned.
        '''
        response = self.url_get(
            'unicef', reverse('perform_pod_action', args=('0',)))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json, {
            'reason': 'Method not allowed'}
        )

    def test_pod_doesnt_exist(self):
        '''
        If the requested pod id is invalid, an appropriate 404 error should be
        returned.
        '''
        with self.settings(PODS=[]):
            from casepro.pods import registry
            reload(registry)
        response = self.url_post_json(
            'unicef', reverse('perform_pod_action', args=('0',)), {})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {
            'reason': 'Pod does not exist'}
        )

    def test_invalid_json(self):
        '''
        If the request has an invalid json body, a correct error response
        should be returned.
        '''
        response = self.url_post(
            'unicef', reverse('perform_pod_action', args=('0',)), body="{")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {
            'reason': 'JSON decode error',
            'details': 'No JSON object could be decoded'
        })

    def test_pod_valid_request(self):
        '''
        If it is a valid post request, the action should be performed.
        '''
        with self.settings(PODS=[{'label': 'base_pod'}]):
            from casepro.pods import registry
            reload(registry)
        response = self.url_post_json(
            'unicef', reverse('perform_pod_action', args=('0',)), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {})
