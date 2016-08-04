from __future__ import unicode_literals

from casepro.pods import Pod, PodPlugin


class DummyPod(Pod):
    pass


class DummyPodPlugin(PodPlugin):
    pod_class = DummyPod
    name = 'casepro.pods.tests.utils'
    label = 'dummy_pod'
    title = 'Dummy Pod'
    controller = 'DummyPodController'
    directive = 'dummy-pod'
    scripts = ('dummy-script.js',)
    styles = ('dummy-style.css',)
