# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Backend errors whose messages are safe to expose to desktop clients."""

from __future__ import annotations


class UserVisibleError(Exception):
    """Marker for bounded, backend-authored messages that may cross D-Bus."""


class UserVisibleValueError(UserVisibleError, ValueError):
    """A client input error with a safe, actionable message."""


class UserVisibleRuntimeError(UserVisibleError, RuntimeError):
    """A backend state error with a safe, actionable message."""


class ConnectorStartupError(UserVisibleRuntimeError):
    """Networking failed after Core finished probing the saved session."""

    def __init__(self, *, logged_in: bool) -> None:
        self.logged_in = logged_in
        prefix = "Your saved Proton session was restored, but " if logged_in else ""
        super().__init__(
            prefix + "VPN networking could not initialize. "
            "Check NetworkManager and retry the service."
        )


class CleanupAdmissionExpired(UserVisibleRuntimeError):
    """Cleanup did not cross its dispatch boundary before the deadline."""

    def __init__(self) -> None:
        super().__init__(
            "Cleanup could not be dispatched before its deadline. "
            "Review the current VPN status before retrying."
        )


class SessionExpiredError(UserVisibleRuntimeError):
    """A Proton session expiry already published as signed-out state."""


class NpsCompletionUnknownError(UserVisibleRuntimeError):
    """The upstream survey side effect may have completed."""


def is_proton_authentication_needed(error: BaseException) -> bool:
    """Classify Core's optional authentication-expiry exception by contract."""
    return type(error).__name__ == "ProtonAPIAuthenticationNeeded"


def bounded_user_message(error: UserVisibleError, fallback: str) -> str:
    """Return only bounded, printable text explicitly marked safe for users."""

    message = str(error).strip()
    if not message or len(message) > 256 or not message.isprintable():
        return fallback
    return message
