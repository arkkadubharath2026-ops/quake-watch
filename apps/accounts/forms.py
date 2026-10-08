"""Sign-up form for ArangoDB accounts (same fields and validation as Django's UserCreationForm)."""

from __future__ import annotations

from typing import Any, cast

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator

from apps.accounts.identity import ArangoUser, create_user
from apps.accounts.repository import UserRepository
from apps.core.arango.client import get_db
from apps.core.errors import Conflict

_DUPLICATE = "A user with that username already exists."


class _Candidate:
    """Attributes UserAttributeSimilarityValidator compares the password against."""

    def __init__(self, username: str, email: str) -> None:
        self.username = username
        self.email = email


class SignupForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    email = forms.EmailField(
        required=False, help_text="Optional. Used only to identify your account."
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label="Password confirmation",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Enter the same password as before, for verification.",
    )

    def clean_username(self) -> str:
        username = str(self.cleaned_data["username"])
        if UserRepository(get_db()).username_taken_ci(username):
            raise forms.ValidationError(_DUPLICATE, code="unique")
        return username

    def clean_password2(self) -> str:
        password1 = self.cleaned_data.get("password1")
        password2 = str(self.cleaned_data.get("password2") or "")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                "The two password fields didn't match.", code="password_mismatch"
            )
        return password2

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        password = cleaned.get("password2")
        if password and "username" in cleaned:
            candidate = _Candidate(str(cleaned["username"]), str(cleaned.get("email") or ""))
            try:
                # The validators only read attributes (similarity check); stubs expect a User.
                password_validation.validate_password(password, cast(Any, candidate))
            except forms.ValidationError as error:
                self.add_error("password2", error)
        return cleaned

    def save(self) -> ArangoUser:
        data: dict[str, Any] = self.cleaned_data
        try:
            return create_user(data["username"], data["password1"], email=data.get("email") or "")
        except Conflict as exc:  # lost a race with a concurrent sign-up
            raise forms.ValidationError(_DUPLICATE, code="unique") from exc
