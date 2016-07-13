from django.test import TestCase

from casepro.pods.registry import (
    get_class_from_app_label, load_pod, get_url_patterns)


class PodRegistryTests(TestCase):
    '''
    Tests related to the casepro.pods.registry module.
    '''
    def test_get_class_from_app_label(self):
        '''
        The get_class_from_app_label function should take an app label and
        return the correct class.
        '''
        from casepro.pods import Pod
        result = get_class_from_app_label('casepro.pods')
        self.assertEqual(result, Pod)

    def test_get_class_from_app_label_invalid(self):
        '''
        Invalid app labels should result in lookup errors.
        '''
        self.assertRaises(LookupError, get_class_from_app_label, 'foo.bar.baz')

    def test_load_pod_app_label(self):
        '''
        The load_pod function should load the pod with the correct app label
        specified by 'type'.
        '''
        from casepro.pods import Pod
        pod_instance = load_pod(0, {'type': 'casepro.pods'})
        self.assertTrue(isinstance(pod_instance, Pod))

    def test_load_pod_index(self):
        '''
        The load_pod function should set the index on the pod config.
        '''
        index = 7
        pod_instance = load_pod(index, {'type': 'casepro.pods'})
        self.assertEqual(pod_instance.config.index, index)

    def test_pods_loaded_on_import(self):
        '''
        On import, the pods specified in the settings file should be loaded
        with correct index numbers and types.
        '''
        with self.settings(PODS=[
                {'type': 'casepro.pods'},
                {'type': 'casepro.pods'}]):
            from casepro.pods import registry, Pod
            reload(registry)

        self.assertEqual(len(registry.pods), 2)
        for i in range(2):
            self.assertTrue(isinstance(registry.pods[i], Pod))
            self.assertEqual(registry.pods[i].config.index, i)

    def test_get_url_patterns(self):
        '''
        The get_url_patterns function should return a list of all of the url
        patterns of all of the pods specified in the settings files.
        '''
        with self.settings(PODS=[
                {'type': 'casepro.pods'},
                {'type': 'casepro.pods'}]):
            from casepro.pods import registry
            reload(registry)

        for i, url_pattern in enumerate(get_url_patterns()):
            self.assertEqual(
                url_pattern.callback, registry.pods[i].request_callback)
            self.assertEqual(url_pattern.regex.pattern, r'read/%d/$' % i)
