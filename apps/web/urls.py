"""Server-rendered pages (PRD §10 information architecture). Data comes from /api/v1."""

from django.urls import path

from apps.web import views

app_name = "pages"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("map/", views.live_map, name="map"),
    path("explorer/", views.explorer, name="explorer"),
    path("events/<str:identifier>/", views.event_detail, name="event"),
    path("analytics/", views.analytics, name="analytics"),
    path("alerts/", views.alerts, name="alerts"),
    path("research/", views.research, name="research"),
    path("status/", views.status, name="status"),
    path("operations/", views.operations, name="operations"),
    path("about/", views.about, name="about"),
]
