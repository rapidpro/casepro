import json

from django.apps import apps
from django.test import TestCase, modify_settings

from casepro.pods import Pod, PodConfig


@modify_settings(INSTALLED_APPS={"append": "casepro.pods.PodPlugin"})
class PodTests(TestCase):
    """
    Tests related to the Pod class.
    """

    def test_config_json(self):
        pod = Pod(apps.get_app_config("base_pod"), PodConfig({"index": 23, "title": "Foo"}))

        self.assertEqual(json.loads(pod.config_json), {"index": 23, "title": "Foo"})
