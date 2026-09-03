# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Backend lifetime management for D-Bus-activated desktop clients."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import re
from time import monotonic

from dbus_fast import Message
from dbus_fast.constants import MessageType

from .controller import BackendController, VpnSnapshot
from .errors import UserVisibleValueError


NameOwnerProbe = Callable[[str], Awaitable[bool]]
_UNIQUE_BUS_NAME = re.compile(r"^:[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$")


async def name_has_owner(bus, name: str) -> bool:
    """Return whether *name* still has an owner on the session bus."""
    reply = await bus.call(
        Message(
            destination="org.freedesktop.DBus",
            path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus",
            member="NameHasOwner",
            signature="s",
            body=[name],
        )
    )
    return bool(
        reply
        and reply.message_type is MessageType.METHOD_RETURN
        and reply.body
        and reply.body[0]
    )


class BackendLifetime:
    """Keep the backend alive only while it owns useful session state.

    Native frontends register their unique D-Bus names as leases. A vanished
    frontend is removed through the authorizer's D-Bus owner-loss event even
    when it cannot unregister cleanly. Ownership is probed once when acquiring
    a lease; no periodic wakeup is required afterward. With no live frontend,
    the service exits only from the fully disconnected, idle state; active
    tunnels and packet captures therefore remain supervised. The same grace
    period also abandons an initialization whose activating frontend has
    disappeared while a desktop Secret Service prompt is still open.
    """

    def __init__(
        self,
        controller: BackendController,
        stopped: asyncio.Event,
        owner_probe: NameOwnerProbe,
        *,
        idle_timeout: float = 10.0,
    ) -> None:
        self._controller = controller
        self._stopped = stopped
        self._owner_probe = owner_probe
        self._idle_timeout = max(0.0, idle_timeout)
        self._clients: set[str] = set()
        # RegisterClient verifies ownership asynchronously.  Remember a
        # per-name retirement generation so an UnregisterClient that overtakes
        # that probe cannot be undone when the older registration resumes.
        self._client_generations: dict[str, int] = {}
        self._pending_client_registrations: dict[str, int] = {}
        self._changed = asyncio.Event()
        self._idle_since: float | None = None
        controller.subscribe(self._on_snapshot)

    @property
    def clients(self) -> frozenset[str]:
        return frozenset(self._clients)

    async def register_client(self, unique_name: str) -> None:
        generation = self.registration_generation(unique_name)
        try:
            if not await self._owner_probe(unique_name):
                raise UserVisibleValueError(
                    "The frontend D-Bus name has no owner"
                )
        except BaseException:
            self.cancel_registration(unique_name, generation)
            raise
        self.register_authorized_client(unique_name, generation)

    def registration_generation(self, unique_name: str) -> int:
        """Capture the retirement generation before an asynchronous probe."""
        self._validate_unique_name(unique_name)
        self._pending_client_registrations[unique_name] = (
            self._pending_client_registrations.get(unique_name, 0) + 1
        )
        return self._client_generations.get(unique_name, 0)

    def cancel_registration(self, unique_name: str, generation: int) -> None:
        """Release tracking for a registration that never reached commit."""
        self._validate_unique_name(unique_name)
        self._finish_registration(unique_name)

    def register_authorized_client(
        self, unique_name: str, generation: int | None = None
    ) -> None:
        """Add a lease whose owner was verified by the ingress authorizer."""
        self._validate_unique_name(unique_name)
        if generation is not None:
            current = generation == self._client_generations.get(unique_name, 0)
            self._finish_registration(unique_name)
            if not current:
                return
        self._clients.add(unique_name)
        self._idle_since = None
        self._changed.set()

    def unregister_client(self, unique_name: str) -> None:
        self._validate_unique_name(unique_name)
        if self._pending_client_registrations.get(unique_name, 0):
            self._client_generations[unique_name] = (
                self._client_generations.get(unique_name, 0) + 1
            )
        else:
            self._client_generations.pop(unique_name, None)
        if unique_name not in self._clients:
            return
        self._clients.remove(unique_name)
        self._idle_since = None
        self._changed.set()

    def _finish_registration(self, unique_name: str) -> None:
        pending = self._pending_client_registrations.get(unique_name, 0)
        if pending <= 1:
            self._pending_client_registrations.pop(unique_name, None)
            self._client_generations.pop(unique_name, None)
            return
        self._pending_client_registrations[unique_name] = pending - 1

    async def run(self) -> None:
        while not self._stopped.is_set():
            self._changed.clear()
            now = monotonic()
            if self._may_exit(self._controller.snapshot):
                if self._idle_since is None:
                    self._idle_since = now
                remaining = self._idle_timeout - (now - self._idle_since)
                if remaining <= 0:
                    self._stopped.set()
                    return
            else:
                self._idle_since = None
                await self._changed.wait()
                continue

            try:
                await asyncio.wait_for(self._changed.wait(), timeout=remaining)
            except TimeoutError:
                pass

    def _may_exit(self, snapshot: VpnSnapshot) -> bool:
        if self._clients:
            return False
        if not snapshot.ready:
            return (
                snapshot.state == "starting"
                and not self._controller.has_pending_startup_recovery()
            )
        return (
            snapshot.state == "disconnected"
            and not snapshot.busy
            and not snapshot.packet_capture_active
        )

    def _on_snapshot(self, _snapshot: VpnSnapshot) -> None:
        self._changed.set()

    @staticmethod
    def _validate_unique_name(unique_name: str) -> None:
        if len(unique_name) > 255 or _UNIQUE_BUS_NAME.fullmatch(unique_name) is None:
            raise UserVisibleValueError(
                "A valid unique frontend D-Bus name is required"
            )
