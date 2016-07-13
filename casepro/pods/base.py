from confmodel import fields, Config as ConfmodelConfig
from django.apps import AppConfig


class PodPlugin(AppConfig):
    pass


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
    url_patterns = ()
    name = 'Default pod name'
    controller = None
    directive = None

    def __init__(self, config):
        self.config = self.config_cls(config)
