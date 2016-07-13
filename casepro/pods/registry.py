from django.conf import settings
import importlib


def get_class_from_string(string):
    '''
    Given a class specified by a string, this will return that class.
    '''
    module_name, cls_name = string.rsplit('.', 1)
    module = importlib.import_module(module_name)
    return getattr(module, cls_name)


def load_pod(index, config):
    '''
    Given the index of the pod, and the config dictionary for the pod, this
    returns the instance of that pod.
    '''
    class_name = config.pop('type')
    config['index'] = index
    return get_class_from_string(class_name)(config)


pods = [
    load_pod(i, c) for i, c in enumerate(settings.PODS)
]


def get_url_patterns():
    '''
    Get the list of URL patterns for all of the pods.
    '''
    return [
        pattern
        for pod in pods
        for pattern in pod.url_patterns
    ]
