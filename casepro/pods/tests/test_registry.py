from importlib import reload

from django.apps import apps
from django.test import TestCase, modify_settings

from casepro.pods.registry import load_pod


@modify_settings(INSTALLED_APPS={"append": "casepro.pods.PodPlugin"})
class PodRegistryTests(TestCase):
    """
    Tests related to the casepro.pods.registry module.
    """

    def test_load_pod_label(self):
        """
        The load_pod function should load the pod with the correct app label specified by 'type'.
        """
        from casepro.pods import Pod

        pod_instance = load_pod(0, {"label": "base_pod"})
        self.assertTrue(isinstance(pod_instance, Pod))

    def test_load_pod_index(self):
        """
        The load_pod function should set the index on the pod config.
        """
        index = 7
        pod_instance = load_pod(index, {"label": "base_pod"})
        self.assertEqual(pod_instance.config.index, index)

    def test_load_pod_title(self):
        """
        The load_pod function should set the config title, or default it title field to the pod type title if it isn't
        given.
        """
        pod = load_pod(23, {"label": "base_pod", "title": "Foo"})
        self.assertEqual(pod.config.title, "Foo")

        pod = load_pod(23, {"label": "base_pod"})
        self.assertEqual(pod.config.title, "Pod")

    def test_load_pod_config(self):
        """
        The load_pod function instantiate and pass through the pod's config.
        """
        from casepro.pods import PodConfig

        index = 7
        pod = load_pod(index, {"label": "base_pod"})
        self.assertTrue(isinstance(pod.config, PodConfig))

    @modify_settings(INSTALLED_APPS={"append": "casepro.pods.PodPlugin"})
    def test_pods_loaded_on_import(self):
        """
        On import, the pods specified in the settings file should be loaded with correct index numbers and types.
        """
        with self.settings(PODS=[{"label": "base_pod"}, {"label": "base_pod"}]):
            from casepro.pods import registry, Pod

            reload(registry)

        self.assertEqual(len(registry.pods), 2)
        for i in range(2):
            pod = registry.pods[i]
            self.assertTrue(isinstance(pod, Pod))
            self.assertEqual(pod.pod_type, apps.get_app_config("base_pod"))
            self.assertEqual(pod.config.index, i)

    @modify_settings(INSTALLED_APPS={"append": "casepro.pods.PodPlugin"})
    def test_pod_types_registered_on_import(self):
        """
        On import, the pod types specified in the settings file should be registered.
        """
        from casepro.pods import registry, PodPlugin

        reload(registry)
        [pod_type] = registry.pod_types
        self.assertTrue(isinstance(pod_type, PodPlugin))
