from __future__ import unicode_literals

import json
from confmodel import fields, Config as ConfmodelConfig
from django.apps import AppConfig


class PodConfig(ConfmodelConfig):
    """
    This is the config that all pods should use as the base for their own config.
    """
    index = fields.ConfigInt(
        "A unique identifier for the specific instance of this pod. Automatically determined and set in the pod"
        "registry.",
        required=True)

    title = fields.ConfigText(
        "The title to show in the UI for this pod",
        default=None)


class Pod(object):
    """
    The base class for all pod plugins.
    """
    def __init__(self, pod_type, config):
        self.pod_type = pod_type
        self.config = config

    @property
    def config_json(self):
        return json.dumps(self.config._config_data)

    def read_data(self, params):
        """Should return the data that should be used to create the display for the pod."""
        return {}

    def perform_action(self, params):
        """Should perform the action specified by params."""
        return {}


class PodPlugin(AppConfig):
    name = 'casepro.pods'
    pod_class = Pod
    config_class = PodConfig

    # django application label, used to determine which pod type to use when loading pods configured in `settings.PODS`
    label = 'base_pod'

    # default title to use when configuring each pod
    title = 'Pod'

    # override to use a different angular controller
    controller = 'PodController'

    # override to use a different angular directive
    directive = 'cp-pod'

    # override with paths to custom scripts that the pod needs
    scripts = ()

    # override with paths to custom styles that the pod needs
    styles = ()
