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
from dbus_fast.validators import is_object_path_valid


SECRET_STORE_WAIT_SECONDS = 120.0
POLL_SECONDS = 5.0
QUERY_SECONDS = 2.0
CLEANUP_SECONDS = 0.5
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


class _PromptDismissed(Exception):
    """Explicit refusal ends this startup admission without another prompt."""


async def _call(bus, destination, path, interface, member, signature, body, *, interactive=False):
    async with asyncio.timeout(None if interactive else QUERY_SECONDS):
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


async def _owner_is_current(bus, owner: str) -> bool:
    current, = await _call(bus, _BUS, "/org/freedesktop/DBus", _BUS,
                           "GetNameOwner", "s", [_SERVICE])
    return current == owner


class _UnlockPrompt:
    """One unlock request for an admission, including provider replacements."""

    def __init__(self) -> None:
        self.requested = False

    async def request(self, bus, owner: str, collection: str) -> None:
        self.requested = True  # Consume before dispatch, even on refusal/error.
        completion: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        prompt_path = None
        completed_signal = False
        prompt_call: asyncio.Task | None = None

        def signal(message):
            nonlocal completed_signal
            if message.message_type is not MessageType.SIGNAL or completion.done():
                return
            if (message.sender == _BUS and message.path == "/org/freedesktop/DBus"
                    and message.interface == _BUS and message.member == "NameOwnerChanged"
                    and message.signature == "sss" and len(message.body) == 3
                    and message.body[0] == _SERVICE and message.body[2] != owner):
                completion.set_exception(ValueError("Secret Service owner changed"))
            elif (message.sender == owner and message.path == prompt_path
                  and message.interface == "org.freedesktop.Secret.Prompt"
                  and message.member == "Completed" and message.signature == "bv"
                  and len(message.body) == 2 and type(message.body[0]) is bool
                  and isinstance(message.body[1], Variant)):
                if message.body[0]:
                    completed_signal = True
                    completion.set_exception(_PromptDismissed())
                elif message.body[1].signature != "ao":
                    completion.set_exception(ValueError("Secret Service prompt result unavailable"))
                else:
                    completed_signal = True
                    completion.set_result(None)

        bus.add_message_handler(signal)
        try:
            for rule in (
                f"type='signal',sender='{owner}',interface='org.freedesktop.Secret.Prompt',member='Completed'",
                f"type='signal',sender='{_BUS}',interface='{_BUS}',path='/org/freedesktop/DBus',"
                f"member='NameOwnerChanged',arg0='{_SERVICE}'",
            ):
                await _call(bus, _BUS, "/org/freedesktop/DBus", _BUS, "AddMatch", "s", [rule])
            if not await _owner_is_current(bus, owner):
                raise ValueError("Secret Service owner changed")
            if completion.done():
                completion.result()
            unlocked, path = await _call(bus, owner, _PATH, "org.freedesktop.Secret.Service",
                                        "Unlock", "ao", [[collection]])
            if (not isinstance(unlocked, list)
                    or not all(isinstance(p, str) and is_object_path_valid(p) for p in unlocked)
                    or not isinstance(path, str) or not is_object_path_valid(path)):
                raise ValueError("Secret Service unlock result unavailable")
            if path == "/":
                return
            prompt_path = path
            if not await _owner_is_current(bus, owner):
                raise ValueError("Secret Service owner changed")
            if completion.done():
                completion.result()
            # Some providers finish the dialog before replying to Prompt().
            # Its RPC and signal share the admission deadline, not the short
            # metadata timeout; either terminal event can end the operation.
            prompt_call = asyncio.create_task(_call(
                bus, owner, prompt_path, "org.freedesktop.Secret.Prompt", "Prompt", "s", [""],
                interactive=True,
            ))
            done, _ = await asyncio.wait({prompt_call, completion}, return_when=asyncio.FIRST_COMPLETED)
            if completion not in done:
                await prompt_call
            await completion
        finally:
            bus.remove_message_handler(signal)
            if not completion.done():
                completion.cancel()
            elif not completion.cancelled():
                completion.exception()  # Also consume a signal received during a failed RPC.
            if prompt_call is not None and not prompt_call.done():
                prompt_call.cancel()
            try:
                if prompt_call is not None:
                    # MessageBus.call awaits a cancellable future; retire that
                    # owned RPC before disconnecting, including signal-first completion.
                    await asyncio.gather(prompt_call, return_exceptions=True)
            finally:
                if prompt_path is not None and not completed_signal:
                    try:
                        async with asyncio.timeout(CLEANUP_SECONDS):
                            await _call(bus, owner, prompt_path, "org.freedesktop.Secret.Prompt",
                                        "Dismiss", "", [])
                    except Exception:
                        pass


async def secret_service_unlocked(*, activate: bool = False, allow_empty: bool = False,
                                  unlock_prompt: _UnlockPrompt | None = None) -> bool:
    """Observe an unlocked collection of the same-user, stable service owner.

    Initial admission may request one provider-owned unlock prompt or admit an
    empty service for keyring-owned collection creation. Lock retries remain
    passive. No path creates collections or accesses secrets; the keyring still
    independently pins and authorizes its provider before using secrets.
    """
    bus: Any = None
    try:
        async with asyncio.timeout(QUERY_SECONDS):
            bus = MessageBus(bus_type=BusType.SESSION)
            await bus.connect()

            async def call(destination, path, interface, member, signature, body):
                return await _call(bus, destination, path, interface, member, signature, body)

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
                    collection = collections.value[0]
                    locked = await is_locked(collection)
                else:
                    return False
            if not await _owner_is_current(bus, owner):
                return False
        if locked and unlock_prompt is not None and not unlock_prompt.requested:
            await unlock_prompt.request(bus, owner, collection)
            # A prompt result is never readiness proof. Re-read the lock and
            # original owner's identity on the same connection before admission.
            async with asyncio.timeout(QUERY_SECONDS):
                locked = await is_locked(collection)
                return locked is False and await _owner_is_current(bus, owner)
        return locked is False
    except _PromptDismissed:
        raise
    except Exception:
        return False
    finally:
        if bus is not None:
            bus.disconnect()
            try:
                async with asyncio.timeout(CLEANUP_SECONDS):
                    await bus.wait_for_disconnect()
            except Exception:
                pass


async def wait_for_secret_service(timeout: float, *, initial_admission: bool = False,
                                  request_unlock: bool = False) -> bool:
    """One admission deadline; interactive startup permits one unlock request."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, timeout)
    activate = initial_admission
    prompt = _UnlockPrompt() if initial_admission and request_unlock else None
    try:
        async with asyncio.timeout_at(deadline):
            while loop.time() < deadline:
                options: dict[str, Any] = {"activate": activate, "allow_empty": True}
                if prompt is not None:
                    options["unlock_prompt"] = prompt
                ready = (await secret_service_unlocked(**options)
                         if initial_admission else await secret_service_unlocked())
                activate = False
                if ready:
                    return True
                await asyncio.sleep(min(POLL_SECONDS, max(0.0, deadline - loop.time())))
    except (TimeoutError, _PromptDismissed):
        return False
    return False
