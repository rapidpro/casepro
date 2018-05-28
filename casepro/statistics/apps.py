from django.apps import AppConfig


class Config(AppConfig):
    name = "casepro.statistics"

    def ready(self):
        from . import signals  # noqa
