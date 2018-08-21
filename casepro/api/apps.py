from django.apps import AppConfig


class Config(AppConfig):
    name = "casepro.api"

    def ready(self):
        from . import signals  # noqa
