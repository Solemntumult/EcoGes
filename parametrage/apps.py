from django.apps import AppConfig


class ParametrageConfig(AppConfig):
    name = 'parametrage'

    def ready(self):
        import parametrage.signals  # noqa: F401
