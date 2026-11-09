# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bounded store admission; collection creation and secrets remain keyring-owned."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from dbus_fast import Message, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, MessageFlag, MessageType


SECRET_STORE_WAIT_SECONDS = 120.0
POLL_SECONDS = 5.0
QUERY_SECONDS = 2.0
_BUS = "org.freedesktop.DBus"
_SERVICE = "org.freedesktop.secrets"
_PATH = "/org/freedesktop/secrets"
_MISSING_OBJECT_ERRORS = {
    "org.freedesktop.DBus.Error.UnknownMethod",
    "org.freedesktop.DBus.Error.UnknownObject",
    "org.freedesktop.Secret.Error.NoSuchObject",
}


def require_secret_service_backend() -> None:
    """Require Proton's public Secret Service backend for this process lifetime.

    SSO re-evaluates backend selection on later operations. Keeping this policy
    in effect prevents a disappearing provider from enabling the JSON fallback.
    Other Proton component overrides retain their existing meaning.
    """
    overrides = os.environ.get("PROTON_LOADER_OVERRIDES", "").split()
    overrides = [value for value in overrides if not value.startswith("keyring=")]
    os.environ["PROTON_LOADER_OVERRIDES"] = " ".join(
        [*overrides, "keyring=secret_service"]
    )


class _MissingCollection(Exception):
    """An absent alias or collection, matching SecretStorage's fallback contract."""


async def secret_service_unlocked(*, activate: bool = False, allow_empty: bool = False) -> bool:
    """Observe an unlocked collection of the same-user, stable service owner.

    Initial admission can request standard activation and admit an empty service
    for keyring-owned collection creation. Lock retries remain passive. Neither
    path unlocks, creates collections, or accesses secrets; the keyring still
    independently pins and authorizes its provider before using secrets.
    """
    bus: Any = None
    try:
        async with asyncio.timeout(QUERY_SECONDS):
            bus = MessageBus(bus_type=BusType.SESSION)
            await bus.connect()

            async def call(destination, path, interface, member, signature, body):
                reply = await bus.call(Message(
                    destination=destination, path=path, interface=interface,
                    member=member, signature=signature, body=body,
                    flags=MessageFlag.NO_AUTOSTART,
                ))
                if reply is None:
                    raise ValueError("Secret Service observation unavailable")
                if destination.startswith(":") and reply.sender != destination:
                    raise ValueError("Secret Service observation owner changed")
                if reply.message_type is MessageType.ERROR and reply.error_name in _MISSING_OBJECT_ERRORS:
                    raise _MissingCollection()
                if reply.message_type is not MessageType.METHOD_RETURN:
                    raise ValueError("Secret Service observation unavailable")
                return reply.body

            if activate:
                try:
                    await call(_BUS, "/org/freedesktop/DBus", _BUS,
                               "StartServiceByName", "su", [_SERVICE, 0])
                except Exception:
                    # Manually started providers need no activation file. The
                    # owner/UID/collection checks below remain authoritative.
                    pass
            owner, = await call(_BUS, "/org/freedesktop/DBus", _BUS,
                                "GetNameOwner", "s", [_SERVICE])
            if not isinstance(owner, str) or not owner.startswith(":"):
                return False
            uid, = await call(_BUS, "/org/freedesktop/DBus", _BUS,
                              "GetConnectionUnixUser", "s", [owner])
            if type(uid) is not int or uid != os.getuid():
                return False
            async def is_locked(collection):
                if (not isinstance(collection, str) or not collection.startswith("/")
                        or collection == "/"):
                    raise ValueError("Secret Service collection unavailable")
                value, = await call(owner, collection, "org.freedesktop.DBus.Properties",
                                    "Get", "ss", ["org.freedesktop.Secret.Collection", "Locked"])
                if not isinstance(value, Variant) or value.signature != "b":
                    raise ValueError("Secret Service collection state unavailable")
                return value.value

            try:
                collection, = await call(owner, _PATH, "org.freedesktop.Secret.Service",
                                         "ReadAlias", "s", ["default"])
                if collection == "/":
                    raise _MissingCollection()
                locked = await is_locked(collection)
            except _MissingCollection:
                collections, = await call(owner, _PATH, "org.freedesktop.DBus.Properties",
                                          "Get", "ss", ["org.freedesktop.Secret.Service", "Collections"])
                if not isinstance(collections, Variant) or collections.signature != "ao":
                    return False
                if not collections.value and allow_empty:
                    locked = False
                elif len(collections.value) == 1:
                    locked = await is_locked(collections.value[0])
                else:
                    return False
            current_owner, = await call(_BUS, "/org/freedesktop/DBus", _BUS,
                                        "GetNameOwner", "s", [_SERVICE])
            return current_owner == owner and locked is False
    except Exception:
        return False
    finally:
        if bus is not None:
            bus.disconnect()
            try:
                async with asyncio.timeout(0.5):
                    await bus.wait_for_disconnect()
            except Exception:
                pass


async def wait_for_secret_service(timeout: float, *, initial_admission: bool = False) -> bool:
    """Observe one store at a time; initial admission permits one activation."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, timeout)
    activate = initial_admission
    try:
        async with asyncio.timeout_at(deadline):
            while loop.time() < deadline:
                ready = (await secret_service_unlocked(activate=activate, allow_empty=True)
                         if initial_admission else await secret_service_unlocked())
                activate = False
                if ready:
                    return True
                await asyncio.sleep(min(POLL_SECONDS, max(0.0, deadline - loop.time())))
    except TimeoutError:
        return False
    return False
