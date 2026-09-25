from django.apps import AppConfig


class IngestionConfig(AppConfig):
    name = "apps.ingestion"
    label = "qw_ingestion"
    default_auto_field = "django.db.models.BigAutoField"
