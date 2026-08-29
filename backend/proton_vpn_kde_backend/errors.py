"""Backend errors whose messages are safe to expose to desktop clients."""

from __future__ import annotations


class UserVisibleError(Exception):
    """Marker for bounded, backend-authored messages that may cross D-Bus."""


class UserVisibleValueError(UserVisibleError, ValueError):
    """A client input error with a safe, actionable message."""


class UserVisibleRuntimeError(UserVisibleError, RuntimeError):
    """A backend state error with a safe, actionable message."""
