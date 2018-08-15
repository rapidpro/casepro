import json

from confmodel import Config as ConfmodelConfig
from confmodel import fields
from django.apps import AppConfig


class PodConfig(ConfmodelConfig):
    """
    This is the config that all pods should use as the base for their own config.
    """

    index = fields.ConfigInt(
        "A unique identifier for the specific instance of this pod. Automatically determined and set in the pod"
        "registry.",
        required=True,
    )

    title = fields.ConfigText("The title to show in the UI for this pod", default=None)


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
        """
        Should return the data that should be used to create the display for the pod.

        For the base implementation, the data should be an object with 'items' and 'actions' keys.

        The items key should be a list of objects, that have 'name' and 'value' keys, with the value of the keys being
        what will be displayed.

        The 'actions' key should be a list of objects, that have 'type', 'name' and 'payload' keys, where type and
        payload is what is sent to the 'perform_action' function to determine which button has been pressed, and 'name'
        is the text that is displayed on the button.

        Each action may include the following optional fields:
            - ``busy_text``: used as the action's corresponding
            button's text while waiting on a response from the pod's api side
            when the action is triggered. Defaults to the value of the ``name``
            field.
            - ``confirm``: whether a confirmation modal should be shown to
            confirm whether the user would like to perform the action. Defaults
            to ``false``.

        Example:
        {
            'items': [
                {
                    'name': 'EDD',
                    'value': '2015-07-18',
                },
            ],
            'actions': [
                {
                    'type': 'remove_edd',
                    'name': 'Remove EDD',
                    'payload': {},
                    'busy_text': 'Removing EDD',
                    'confirm': True
                },
            ],
        }
        """
        return {}

    def perform_action(self, type_, params):
        """
        Should perform the action specified by the type and params (which are specified in the read function).

        Returns a tuple (success, payload), where 'success' is a boolean value indicating whether the action was
        successful or not. If true, a case action note will be created.

        For the base implementation, payload is an object with a 'message' key, which is the error message if success
        is false, or the message to place in the case action note if success is true.
        """
        return (False, {"message": ""})


class PodPlugin(AppConfig):
    name = "casepro.pods"
    pod_class = Pod
    config_class = PodConfig

    # django application label, used to determine which pod type to use when loading pods configured in `settings.PODS`
    label = "base_pod"

    # default title to use when configuring each pod
    title = "Pod"

    # override to use a different angular controller
    controller = "PodController"

    # override to use a different angular directive
    directive = "cp-pod"

    # override with paths to custom scripts that the pod needs
    scripts = ()

    # override with paths to custom styles that the pod needs
    styles = ()
