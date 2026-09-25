from django.contrib import admin
from django.urls import path

from apps.operations import health

urlpatterns = [
    path("health/live", health.live, name="health-live"),
    path("health/ready", health.ready, name="health-ready"),
    path("django-admin/", admin.site.urls),
]
