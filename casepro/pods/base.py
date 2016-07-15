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


class Pod(object):
    '''
    The base class for all pod plugins.
    '''
    config_cls = PodConfig
    name = 'Default pod name'
    controller = None
    directive = None

    def __init__(self, config):
        self.config = self.config_cls(config)

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
