from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "qw_core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core import task_context  # noqa: F401  (registers Celery correlation-id signals)
