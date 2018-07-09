from django.apps import apps
from django.conf import settings

from casepro.pods.base import PodPlugin


def load_pod(index, config):
    """
    Given the index of the pod, and the config dictionary for the pod, this
    returns the instance of that pod.
    """
    config = config.copy()
    pod_type = apps.get_app_config(config.pop("label"))

    config["index"] = index
    config.setdefault("title", pod_type.title)

    return pod_type.pod_class(pod_type, pod_type.config_class(config))


pods = tuple(load_pod(i, c) for i, c in enumerate(settings.PODS))


pod_types = tuple(app for app in apps.get_app_configs() if isinstance(app, PodPlugin))
