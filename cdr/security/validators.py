"""Custom Django password validators."""
from __future__ import annotations

import re

from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import PasswordHistory


class StrongPasswordValidator:
    """Min length 12 + at least one upper / lower / digit / symbol."""

    MIN_LENGTH = 12

    def validate(self, password, user=None):
        errors = []
        if len(password) < self.MIN_LENGTH:
            errors.append(_(f"Password must be at least {self.MIN_LENGTH} characters."))
        if not re.search(r'[A-Z]', password):
            errors.append(_("Password must include an uppercase letter."))
        if not re.search(r'[a-z]', password):
            errors.append(_("Password must include a lowercase letter."))
        if not re.search(r'\d', password):
            errors.append(_("Password must include a digit."))
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password):
            errors.append(_("Password must include a symbol."))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            f"Use at least {self.MIN_LENGTH} characters with upper- and lower-case "
            "letters, digits, and at least one symbol."
        )


class PasswordHistoryValidator:
    """Prevents reuse of the last N passwords (default 5)."""

    def __init__(self, history_size: int = 5):
        self.history_size = history_size

    def validate(self, password, user=None):
        if user is None or user.pk is None:
            return
        recent = PasswordHistory.objects.filter(user=user).order_by('-created_at')[:self.history_size]
        for entry in recent:
            if check_password(password, entry.password_hash):
                raise ValidationError(_(
                    f"Password matches one of your last {self.history_size} passwords."
                ))

    def get_help_text(self):
        return _(f"Cannot reuse any of your last {self.history_size} passwords.")
