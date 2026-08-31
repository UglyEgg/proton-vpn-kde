# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bounded packet-capture lifecycle over Proton Core's public connection API."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Callable

from .errors import UserVisibleRuntimeError, UserVisibleValueError


PACKET_CAPTURE_MAX_SECONDS = 15 * 60
MAX_ACCEPTED_CORE_CAPTURE_BYTES = 512 * 1024 * 1024


class PacketCaptureCoordinator:
    """Own one packet-capture generation and its mandatory safety timeout."""

    def __init__(
        self,
        max_seconds: float,
        notify: Callable[[str | None], None],
    ) -> None:
        self._max_seconds = max(0.01, float(max_seconds))
        self._notify = notify
        self.active = False
        self.watchdog_task: asyncio.Task | None = None
        self._generation = 0
        self._connection: Any = None
        self._stop_lock = asyncio.Lock()

    async def start(self, connector: Any, directory_path: str) -> None:
        if self.active:
            raise UserVisibleRuntimeError("Packet capture is already active")
        if type(connector.current_state).__name__.lower() != "connected":
            raise UserVisibleRuntimeError(
                "Connect the VPN before starting packet capture"
            )
        connection = connector.current_connection
        if connection is None or not self.connection_supports_capture(connection):
            raise UserVisibleRuntimeError(
                "The selected protocol does not support packet capture"
            )
        capture_settings = getattr(connection.settings, "packet_capture", None)
        core_max_bytes = getattr(capture_settings, "max_bytes", None)
        if (
            capture_settings is None
            or isinstance(core_max_bytes, bool)
            or not isinstance(core_max_bytes, int)
            or core_max_bytes <= 0
            or core_max_bytes > MAX_ACCEPTED_CORE_CAPTURE_BYTES
        ):
            raise UserVisibleRuntimeError(
                "The installed Proton Core does not expose a supported packet-capture byte limit"
            )
        path = Path(directory_path)
        if not path.is_absolute():
            raise UserVisibleValueError("Select a valid packet-capture folder")
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise UserVisibleValueError(
                "Select an existing packet-capture folder"
            ) from error
        if not resolved.is_dir() or not os.access(resolved, os.W_OK | os.X_OK):
            raise UserVisibleValueError("Select a writable packet-capture folder")
        try:
            capture_settings.directory_path = str(resolved)
            await connection.start_packet_capture()
        except Exception:
            raise UserVisibleRuntimeError(
                "Proton could not start packet capture"
            ) from None
        self._generation += 1
        generation = self._generation
        self.active = True
        self._connection = connection
        self.cancel_watchdog()
        self.watchdog_task = asyncio.create_task(
            self._watchdog(generation, connection)
        )
        self._notify(None)

    async def stop(self) -> None:
        if not self.active:
            self.cancel_watchdog()
            return
        await self._stop_generation(
            self._generation,
            self._connection,
            attempts=1,
            safety_limit=False,
        )

    def cancel_watchdog(self) -> None:
        task = self.watchdog_task
        self.watchdog_task = None
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if task is not None and task is not current_task:
            task.cancel()

    def finish(self) -> None:
        self.active = False
        self._connection = None
        self._generation += 1
        self.cancel_watchdog()

    @staticmethod
    def connection_supports_capture(connection: Any) -> bool:
        try:
            return bool(connection.supports_packet_capture())
        except (AttributeError, TypeError):
            return False

    async def _watchdog(self, generation: int, connection: Any) -> None:
        try:
            await asyncio.sleep(self._max_seconds)
            await self._stop_generation(
                generation,
                connection,
                attempts=3,
                safety_limit=True,
            )
        except asyncio.CancelledError:
            return

    async def _stop_generation(
        self,
        generation: int,
        connection: Any,
        *,
        attempts: int,
        safety_limit: bool,
    ) -> bool:
        """Stop one capture generation exactly once across every caller."""
        async with self._stop_lock:
            if (
                generation != self._generation
                or not self.active
                or connection is not self._connection
            ):
                return False

            for attempt in range(attempts):
                try:
                    if connection is not None:
                        await connection.stop_packet_capture()
                    break
                except Exception:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(1.0)
                        continue
                    if safety_limit:
                        self._notify(
                            "Packet capture reached its time limit but Proton Core could not stop it"
                        )
                        return False
                    raise UserVisibleRuntimeError(
                        "Proton could not stop packet capture"
                    ) from None

            if generation != self._generation or connection is not self._connection:
                return False
            self.finish()
            self._notify(
                "Packet capture stopped at the 15-minute safety limit"
                if safety_limit
                else None
            )
            return True
