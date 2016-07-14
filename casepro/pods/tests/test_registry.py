from django.test import TestCase, modify_settings

from casepro.pods.registry import (
    get_class_from_app_label, load_pod)


@modify_settings(INSTALLED_APPS={
    'append': 'casepro.pods.PodPlugin',
})
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
        result = get_class_from_app_label('base_pod')
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
        pod_instance = load_pod(0, {'app_label': 'base_pod'})
        self.assertTrue(isinstance(pod_instance, Pod))

    def test_load_pod_index(self):
        '''
        The load_pod function should set the index on the pod config.
        '''
        index = 7
        pod_instance = load_pod(index, {'app_label': 'base_pod'})
        self.assertEqual(pod_instance.config.index, index)

    def test_pods_loaded_on_import(self):
        '''
        On import, the pods specified in the settings file should be loaded
        with correct index numbers and types.
        '''
        with self.settings(PODS=[
                {'app_label': 'base_pod'},
                {'app_label': 'base_pod'}]):
            from casepro.pods import registry, Pod
            reload(registry)

        self.assertEqual(len(registry.pods), 2)
        for i in range(2):
            self.assertTrue(isinstance(registry.pods[i], Pod))
            self.assertEqual(registry.pods[i].config.index, i)
