from django.urls import include, path

from apps.operations import health

urlpatterns = [
    path("health/live", health.live, name="health-live"),
    path("health/ready", health.ready, name="health-ready"),
    path("api/v1/", include("config.api_urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("", include("apps.web.urls")),
]
