"""Thread-safe interaction bridge for Proton's FIDO2 implementation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from threading import Event, Lock
from typing import Optional


StatusCallback = Callable[[str, str], None]


class FidoInteraction:
    """Bridges blocking security-key callbacks into backend auth snapshots."""

    def __init__(
        self, loop: asyncio.AbstractEventLoop, status_callback: StatusCallback
    ):
        self._loop = loop
        self._status_callback = status_callback
        self._pin_ready: Event | None = None
        self._pin: str | None = None
        self._lock = Lock()
        self.cancel_assertion = Event()

    @property
    def cancelled(self) -> bool:
        return self.cancel_assertion.is_set()

    def prompt_up(self) -> None:
        self._publish(
            "fido_touch",
            "Touch your security key to continue",
        )

    def request_key_selection(self) -> None:
        self._publish(
            "fido_select",
            "Multiple security keys were found; touch the one you want to use",
        )

    def request_pin(self, *_args, **_kwargs) -> Optional[str]:
        with self._lock:
            self._pin = None
            self._pin_ready = Event()
            pin_ready = self._pin_ready
        self._publish("fido_pin", "Enter the PIN for your security key")
        pin_ready.wait()
        with self._lock:
            pin = self._pin
            self._pin = None
            self._pin_ready = None
        return pin

    def request_uv(self, *_args, **_kwargs) -> bool:
        return not self.cancelled

    def provide_pin(self, pin: str) -> bool:
        with self._lock:
            if not self._pin_ready:
                return False
            self._pin = pin
            self._pin_ready.set()
            return True

    def cancel(self) -> None:
        self.cancel_assertion.set()
        with self._lock:
            if self._pin_ready:
                self._pin_ready.set()

    def _publish(self, state: str, message: str) -> None:
        self._loop.call_soon_threadsafe(self._status_callback, state, message)
