# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Sender-bound authorization for the exported session D-Bus interface."""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable, Iterable
import os
from pathlib import Path
import stat

from dbus_fast import Message
from dbus_fast.constants import MessageType

from .dbus_contract import (
    HANDSHAKE_METHODS,
    INTERFACE_NAME,
    OBJECT_PATH,
    PROTECTED_METHODS,
    READ_ONLY_METHODS,
    SECRET_DESCRIPTOR_METHODS,
    Error,
)


BACKEND_OBJECT_PATH = OBJECT_PATH
BACKEND_INTERFACE = INTERFACE_NAME
UNAUTHORIZED_ERROR = Error.UNAUTHORIZED
UNAUTHORIZED_MESSAGE = "This application is not authorized to control the VPN"
INVALID_SECRET_ERROR = Error.INVALID_SECRET_PAYLOAD
INVALID_SECRET_MESSAGE = "The protected payload is invalid or no longer valid"
INVALID_ARGUMENTS_ERROR = "org.freedesktop.DBus.Error.InvalidArgs"
INVALID_ARGUMENTS_MESSAGE = "Unexpected Unix file descriptors"
_NAME_OWNER_MATCH = (
    "sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',"
    "path='/org/freedesktop/DBus',member='NameOwnerChanged'"
)

_request_sender: contextvars.ContextVar[str] = contextvars.ContextVar(
    "proton_vpn_kde_request_sender", default=":direct.test"
)
IdentityProbe = Callable[[str], Awaitable[bool]]
OwnerProbe = Callable[[str], Awaitable[bool]]


def current_request_sender() -> str:
    """Return the actual unique sender captured at the bus ingress boundary."""
    return _request_sender.get()


def close_unix_fds(file_descriptors: Iterable[int]) -> None:
    """Close transferred descriptors on a path that rejects before dispatch."""
    for file_descriptor in file_descriptors:
        try:
            os.close(file_descriptor)
        except OSError:
            pass


class ClientAuthorizer:
    """Authenticate native clients and reject unauthorized state changes."""

    def __init__(
        self,
        bus,
        trusted_executables: Iterable[str],
        *,
        enforce_identity: bool = True,
        identity_probe: IdentityProbe | None = None,
        owner_probe: OwnerProbe | None = None,
    ) -> None:
        self._bus = bus
        self._trusted_executables = frozenset(
            str(Path(path).resolve()) for path in trusted_executables if path
        )
        self._enforce_identity = enforce_identity
        self._identity_probe = identity_probe or self._probe_identity
        self._owner_probe = owner_probe or self._name_has_owner
        self._authorized: set[str] = set()
        self._revocation_callbacks: list[Callable[[str], None]] = []

    @property
    def authorized_senders(self) -> frozenset[str]:
        return frozenset(self._authorized)

    def subscribe_revocation(self, callback: Callable[[str], None]) -> None:
        self._revocation_callbacks.append(callback)

    async def install(self) -> None:
        reply = await self._bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="AddMatch",
                signature="s",
                body=[_NAME_OWNER_MATCH],
            )
        )
        if reply.message_type is not MessageType.METHOD_RETURN:
            raise RuntimeError(
                "The D-Bus sender revocation watch could not be installed"
            )

    async def uninstall(self) -> None:
        try:
            await self._bus.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="RemoveMatch",
                    signature="s",
                    body=[_NAME_OWNER_MATCH],
                )
            )
        except Exception:
            pass

    async def authorize(self, claimed_sender: str) -> None:
        sender = current_request_sender()
        if not sender.startswith(":") or claimed_sender != sender:
            raise PermissionError(UNAUTHORIZED_MESSAGE)
        if self._enforce_identity:
            if not await self._identity_probe(sender):
                raise PermissionError(UNAUTHORIZED_MESSAGE)
            if not await self._owner_probe(sender):
                raise PermissionError(UNAUTHORIZED_MESSAGE)
        self._authorized.add(sender)

    def require_authorized_sender(self) -> str:
        sender = current_request_sender()
        if sender not in self._authorized:
            raise PermissionError(UNAUTHORIZED_MESSAGE)
        return sender

    def revoke(self, sender: str) -> None:
        if sender not in self._authorized:
            return
        self._authorized.discard(sender)
        for callback in tuple(self._revocation_callbacks):
            callback(sender)

    def message_handler(self, message: Message) -> Message | bool | None:
        """Capture the real sender and enforce the complete method policy."""
        if (
            message.message_type is MessageType.SIGNAL
            and message.sender == "org.freedesktop.DBus"
            and message.path == "/org/freedesktop/DBus"
            and message.interface == "org.freedesktop.DBus"
            and message.member == "NameOwnerChanged"
            and len(message.body) == 3
            and not message.body[2]
        ):
            self.revoke(str(message.body[0]))
            return None

        if (
            message.message_type is not MessageType.METHOD_CALL
            or message.path != BACKEND_OBJECT_PATH
            or message.interface != BACKEND_INTERFACE
        ):
            return None

        sender = message.sender or ""
        _request_sender.set(sender)
        member = message.member or ""
        if member in SECRET_DESCRIPTOR_METHODS:
            valid_descriptor_call = (
                message.signature == "h"
                and len(message.body) == 1
                and type(message.body[0]) is int
                and message.body[0] == 0
                and len(message.unix_fds) == 1
            )
            if not valid_descriptor_call:
                close_unix_fds(message.unix_fds)
                return Message.new_error(
                    message,
                    INVALID_SECRET_ERROR,
                    INVALID_SECRET_MESSAGE,
                )
        elif message.unix_fds:
            # D-Bus transports ancillary descriptors independently from the
            # declared method signature. No ordinary method adopts them, so
            # reject and close them before dbus-fast dispatch can lose track
            # of their ownership.
            close_unix_fds(message.unix_fds)
            return Message.new_error(
                message,
                INVALID_ARGUMENTS_ERROR,
                INVALID_ARGUMENTS_MESSAGE,
            )
        if not self._enforce_identity and sender.startswith(":"):
            # --demo is deterministic and cannot touch credentials, Core, or
            # networking. Its isolated smoke clients remain intentionally open.
            self._authorized.add(sender)
        authorized = sender in self._authorized
        if member in READ_ONLY_METHODS or member in HANDSHAKE_METHODS:
            return None
        if member in PROTECTED_METHODS and authorized:
            return None

        # Unknown future exports are protected by default. The descriptors have
        # already crossed the process boundary, so rejection owns their cleanup.
        close_unix_fds(message.unix_fds)
        return Message.new_error(
            message,
            UNAUTHORIZED_ERROR,
            UNAUTHORIZED_MESSAGE,
        )

    async def _probe_identity(self, sender: str) -> bool:
        try:
            uid = await self._dbus_uint("GetConnectionUnixUser", sender)
            pid = await self._dbus_uint("GetConnectionUnixProcessID", sender)
            if uid != os.getuid() or pid <= 1:
                return False
            executable = Path(f"/proc/{pid}/exe").resolve(strict=True)
            if str(executable) not in self._trusted_executables:
                return False
            metadata = executable.stat()
            if metadata.st_uid != 0 or not stat.S_ISREG(metadata.st_mode):
                return False
            if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                return False
            environment = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
            blocked = (
                b"LD_PRELOAD=",
                b"LD_AUDIT=",
                b"LD_LIBRARY_PATH=",
                b"KDE_PLUGIN_PATH=",
                b"QT_PLUGIN_PATH=",
                b"QT_QPA_PLATFORM_PLUGIN_PATH=",
                b"QML_IMPORT_PATH=",
                b"QML2_IMPORT_PATH=",
            )
            return not any(
                entry.startswith(prefix) for entry in environment for prefix in blocked
            )
        except (OSError, ValueError, TypeError):
            return False

    async def _dbus_uint(self, member: str, sender: str) -> int:
        reply = await self._bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member=member,
                signature="s",
                body=[sender],
            )
        )
        if reply.message_type is not MessageType.METHOD_RETURN or not reply.body:
            return -1
        return int(reply.body[0])

    async def _dbus_bool(self, member: str, sender: str) -> bool:
        reply = await self._bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member=member,
                signature="s",
                body=[sender],
            )
        )
        return bool(
            reply.message_type is MessageType.METHOD_RETURN
            and reply.body
            and reply.body[0]
        )

    async def _name_has_owner(self, sender: str) -> bool:
        return await self._dbus_bool("NameHasOwner", sender)
