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
        self._changed = asyncio.Event()
        self._idle_since: float | None = None
        controller.subscribe(self._on_snapshot)

    @property
    def clients(self) -> frozenset[str]:
        return frozenset(self._clients)

    async def register_client(self, unique_name: str) -> None:
        self._validate_unique_name(unique_name)
        if not await self._owner_probe(unique_name):
            raise UserVisibleValueError("The frontend D-Bus name has no owner")
        self._clients.add(unique_name)
        self._idle_since = None
        self._changed.set()

    def unregister_client(self, unique_name: str) -> None:
        self._validate_unique_name(unique_name)
        if unique_name not in self._clients:
            return
        self._clients.remove(unique_name)
        self._idle_since = None
        self._changed.set()

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
            return snapshot.state == "starting"
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
