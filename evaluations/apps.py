from django.apps import AppConfig


class EvaluationsConfig(AppConfig):
    name = 'evaluations'

    def ready(self):
        import evaluations.signals  # noqa: F401
