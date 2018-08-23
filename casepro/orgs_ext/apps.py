from django.apps import AppConfig


class Config(AppConfig):
    name = "casepro.orgs_ext"

    def ready(self):
        from . import signals  # noqa
