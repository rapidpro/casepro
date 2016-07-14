from django.test import TestCase

from casepro.pods import Pod, PodConfig


class PodTests(TestCase):
    '''
    Tests related to the Pod class.
    '''
    def test_config_on_instantiation(self):
        '''
        When a new Pod object is created, it should have a `config` variable
        with the validated config.
        '''
        pod = Pod({'index': 0})
        self.assertTrue(isinstance(pod.config, PodConfig))
        self.assertEqual(pod.config.index, 0)
