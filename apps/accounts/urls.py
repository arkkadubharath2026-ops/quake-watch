from django.contrib.auth.views import LogoutView
from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.QuakeWatchLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),  # POST only (Django ≥ 5)
    path("signup/", views.signup, name="signup"),
]
