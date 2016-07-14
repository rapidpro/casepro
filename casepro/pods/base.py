from confmodel import fields, Config as ConfmodelConfig
from django.apps import AppConfig


class PodConfig(ConfmodelConfig):
    '''
    This is the config that all pods should use as the base for their own
    config.
    '''
    index = fields.ConfigInt(
        "A unique identifier for the specific instance of this pod."
        "Automatically determined and set in the pod registry.",
        required=True)

    title = fields.ConfigText(
        "The title to show in the UI for this pod",
        default=None)


class Pod(object):
    '''
    The base class for all pod plugins.
    '''
    def __init__(self, pod_type, config):
        self.pod_type = pod_type
        self.config = config

    def read_data(self, params):
        '''Should return the data that should be used to create the display
        for the pod.'''
        return {}

    def perform_action(self, params):
        '''Should perform the action specified by params.'''
        return {}


class PodPlugin(AppConfig):
    name = 'casepro.pods'
    label = 'base_pod'
    pod_class = Pod
    config_class = PodConfig

    title = 'Pod'

    controller = None

    directive = None
