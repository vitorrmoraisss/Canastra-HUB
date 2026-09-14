# matching/apps.py
from django.apps import AppConfig


class MatchingConfig(AppConfig):
    name = "matching"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import matching.signals  # noqa
