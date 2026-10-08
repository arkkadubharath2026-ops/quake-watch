from django.apps import AppConfig


class JobsConfig(AppConfig):
    name = "apps.jobs"
    label = "qw_jobs"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from django.utils.module_loading import autodiscover_modules

        autodiscover_modules("tasks")  # every app's tasks.py registers its job tasks
