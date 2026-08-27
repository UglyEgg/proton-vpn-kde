"""Desktop-neutral asyncio VPN reconnection service."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import os
import random
import shutil
from typing import Any


StatusCallback = Callable[[str], None]
ConditionProbe = Callable[[], Awaitable[bool]]
DelayFactory = Callable[[int], float]


async def network_route_available() -> bool:
    """Match Proton's route-based connectivity check without GLib polling."""
    ip_command = shutil.which("ip")
    if not ip_command:
        return False
    process = await asyncio.create_subprocess_exec(
        ip_command,
        "route",
        "get",
        "192.0.2.1",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return await process.wait() == 0


class LogindSessionProbe:
    """Reads the current session's LockedHint from systemd-logind."""

    def __init__(self):
        self._bus: Any = None
        self._properties: Any = None

    async def is_unlocked(self) -> bool:
        try:
            await self._ensure_proxy()
            locked = await self._properties.call_get(
                "org.freedesktop.login1.Session", "LockedHint"
            )
            return not bool(locked.value)
        except Exception:
            # Preserve the official client's confinement fallback: when logind
            # is unavailable, allow the network condition to govern retries.
            return True

    async def close(self) -> None:
        if self._bus:
            self._bus.disconnect()
            self._bus = None
            self._properties = None

    async def _ensure_proxy(self) -> None:
        if self._properties:
            return

        from dbus_fast.aio import MessageBus
        from dbus_fast.constants import BusType

        self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        manager_path = "/org/freedesktop/login1"
        manager_intro = await self._bus.introspect(
            "org.freedesktop.login1", manager_path
        )
        manager_object = self._bus.get_proxy_object(
            "org.freedesktop.login1", manager_path, manager_intro
        )
        manager = manager_object.get_interface("org.freedesktop.login1.Manager")
        session_path = await manager.call_get_session_by_pid(os.getpid())

        session_intro = await self._bus.introspect(
            "org.freedesktop.login1", session_path
        )
        session_object = self._bus.get_proxy_object(
            "org.freedesktop.login1", session_path, session_intro
        )
        self._properties = session_object.get_interface(
            "org.freedesktop.DBus.Properties"
        )


class AsyncReconnector:
    """Reconnect dropped Proton connections without a GLib main loop."""

    _NO_RETRY_EVENTS = {
        "AuthDenied",
        "MaximumSessionsReached",
        "NotYetValidCertificate",
        "TwoFARequired",
    }

    def __init__(
        self,
        connector: Any,
        refresher: Any,
        status_callback: StatusCallback | None = None,
        network_probe: ConditionProbe = network_route_available,
        session_probe: LogindSessionProbe | None = None,
        delay_factory: DelayFactory | None = None,
    ):
        self._connector = connector
        self._refresher = refresher
        self._status_callback = status_callback or (lambda _message: None)
        self._network_probe = network_probe
        self._session_probe = session_probe or LogindSessionProbe()
        self._delay_factory = delay_factory or self._retry_delay
        self._retry_task: asyncio.Task | None = None
        self._retry_counter = 0
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def retry_counter(self) -> int:
        return self._retry_counter

    def enable(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._connector.register(self)
        self.status_update(self._connector.current_state)

    async def disable(self) -> None:
        if self._enabled:
            self._connector.unregister(self)
        self._enabled = False
        self._reset()
        await self._session_probe.close()

    def status_update(self, state: Any) -> None:
        if not self._enabled:
            return
        state_name = type(state).__name__
        if state_name in {"Connected", "Disconnected"}:
            self._reset()
            self._status_callback("")
            return
        if state_name != "Error":
            return

        event = getattr(getattr(state, "context", None), "event", None)
        event_name = type(event).__name__
        if event_name == "ExpiredCertificate":
            self._status_callback("Refreshing the VPN certificate…")
            self._refresher.force_refresh_certificate()
            return
        if event_name in self._NO_RETRY_EVENTS:
            self._reset()
            self._status_callback(
                "Automatic reconnection is unavailable for this error"
            )
            return
        self._schedule_retry()

    def _schedule_retry(self) -> bool:
        if not self._enabled or self._retry_task:
            return False
        delay = self._delay_factory(self._retry_counter)
        self._status_callback(f"Reconnecting in {delay:.1f} seconds…")
        self._retry_task = asyncio.create_task(self._retry_after(delay))
        return True

    async def _retry_after(self, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        self._retry_task = None
        if type(self._connector.current_state).__name__ != "Error":
            self._reset()
            return
        if not await self._network_probe():
            self._retry_counter += 1
            self._status_callback("Waiting for network connectivity…")
            self._schedule_retry()
            return
        if not await self._session_probe.is_unlocked():
            self._retry_counter += 1
            self._status_callback("Waiting for the Plasma session to unlock…")
            self._schedule_retry()
            return

        connection = self._connector.current_connection
        if not connection:
            self._status_callback("The previous VPN connection is unavailable")
            return

        try:
            logical_server = self._refresher.server_list.get_by_id(connection.server_id)
            vpn_server = self._connector.get_vpn_server(
                logical_server, self._refresher.client_config
            )
            self._retry_counter += 1
            self._status_callback("Reconnecting…")
            await self._connector.connect(
                vpn_server, connection.protocol, connection.backend
            )
        except Exception as error:
            self._status_callback(f"Reconnection failed: {error}")
            self._schedule_retry()

    def _reset(self) -> None:
        current_task = asyncio.current_task()
        if self._retry_task and self._retry_task is not current_task:
            self._retry_task.cancel()
        self._retry_task = None
        self._retry_counter = 0

    @staticmethod
    def _retry_delay(retry_counter: int) -> float:
        # Match Proton's exponential jitter while capping pathological outages.
        return min(2**retry_counter * random.uniform(0.9, 1.1), 60.0)
