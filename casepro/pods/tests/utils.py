import json

from casepro.pods import Pod, PodPlugin


class DummyPod(Pod):
    pass


class DummyPodPlugin(PodPlugin):
    pod_class = DummyPod
    name = "casepro.pods.tests.utils"
    label = "dummy_pod"
    title = "Dummy Pod"
    controller = "DummyPodController"
    directive = "dummy-pod"
    scripts = ("dummy-script.js",)
    styles = ("dummy-style.css",)


class SuccessActionPod(Pod):
    def perform_action(self, type_, params):
        """
        Returns a successful action result with a message containing the type and params.
        """
        return (True, {"message": "Type %s Params %s" % (type_, json.dumps(params))})


class SuccessActionPlugin(DummyPodPlugin):
    pod_class = SuccessActionPod
    label = "success_pod"
