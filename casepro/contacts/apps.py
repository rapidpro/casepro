from django.apps import AppConfig


class Config(AppConfig):
    name = "casepro.contacts"

    def ready(self):
        from . import signals  # noqa
