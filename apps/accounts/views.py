"""Sign up, log in (with lockout feedback) and log out. Accounts live in ArangoDB (ADR-015)."""

from __future__ import annotations

from typing import Any, cast

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts import security
from apps.accounts.forms import SignupForm
from apps.operations.audit import client_ip

LOCKED_MESSAGE = (
    "Too many sign-in attempts. For your security, sign-in is paused for up to 15 minutes."
)


class QuakeWatchLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_invalid(self, form: AuthenticationForm) -> HttpResponse:
        username = form.data.get("username", "")
        if username and security.is_locked(username, client_ip(self.request.META)):
            form.errors.clear()
            form.add_error(None, LOCKED_MESSAGE)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        return {**super().get_context_data(**kwargs), "nav_active": "login"}


@require_http_methods(["GET", "POST"])
def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("pages:dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = form.save()
        except ValidationError as error:  # a concurrent sign-up took the username
            form.add_error("username", error)
        else:
            backend = "apps.accounts.backends.ThrottledModelBackend"
            login(request, cast(Any, user), backend=backend)  # stubs expect the ORM User
            messages.success(request, f"Welcome, {user.get_username()}. Your account is ready.")
            return redirect("pages:dashboard")
    status = 400 if request.method == "POST" else 200
    context = {"form": form, "nav_active": "signup"}
    return render(request, "accounts/signup.html", context, status=status)
