from django.conf.urls import url
from django.test import TestCase

from casepro.pods.registry import (
    get_class_from_string, load_pod, get_url_patterns)


class PodRegistryTests(TestCase):
    '''
    Tests related to the casepro.pods.registry module.
    '''
    def test_get_class_from_string(self):
        '''
        The get_class_from_string function should take a string and return
        the correct class.
        '''
        from casepro.pods import Pod
        result = get_class_from_string('casepro.pods.Pod')
        self.assertEqual(result, Pod)

    def test_get_class_from_string_invalid(self):
        '''
        Invalid class names should result in import errors.
        '''
        self.assertRaises(ImportError, get_class_from_string, 'foo.bar.baz')

    def test_load_pod_class_name(self):
        '''
        The load_pod function should load the pod with the correct class name
        specified by 'type'.
        '''
        from casepro.pods import Pod
        pod_instance = load_pod(0, {'type': 'casepro.pods.Pod'})
        self.assertTrue(isinstance(pod_instance, Pod))

    def test_load_pod_index(self):
        '''
        The load_pod function should set the index on the pod config.
        '''
        index = 7
        pod_instance = load_pod(index, {'type': 'casepro.pods.Pod'})
        self.assertEqual(pod_instance.config.index, index)

    def test_pods_loaded_on_import(self):
        '''
        On import, the pods specified in the settings file should be loaded
        with correct index numbers and types.
        '''
        with self.settings(PODS=[
                {'type': 'casepro.pods.Pod'},
                {'type': 'casepro.pods.Pod'}]):
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
                {'type': 'casepro.pods.Pod'},
                {'type': 'casepro.pods.Pod'}]):
            from casepro.pods import registry
            reload(registry)

        for i, pod in enumerate(registry.pods):
            pod.url_patterns = [url('', None, name=i)]

        for i, url_pattern in enumerate(get_url_patterns()):
            self.assertEqual(url_pattern.name, i)
