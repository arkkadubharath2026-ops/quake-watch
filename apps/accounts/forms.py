from __future__ import annotations

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignupForm(UserCreationForm[User]):
    email = forms.EmailField(
        required=False, help_text="Optional. Used only to identify your account."
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
