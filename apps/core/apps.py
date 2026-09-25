from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "qw_core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from django.utils.module_loading import autodiscover_modules

        from apps.core import task_context  # noqa: F401  (registers Celery correlation-id signals)

        # Import every app's repository module so its NamedQuery objects join the AQL catalog.
        autodiscover_modules("repository")
