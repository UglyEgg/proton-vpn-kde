# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bounded packet-capture lifecycle over Proton Core's public connection API."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time
from typing import Any, Callable

from .capture_recovery import PacketCaptureRecoveryJournal
from .errors import UserVisibleRuntimeError, UserVisibleValueError


PACKET_CAPTURE_MAX_SECONDS = 15 * 60
PACKET_CAPTURE_STOP_ATTEMPT_SECONDS = 5.0
MAX_ACCEPTED_CORE_CAPTURE_BYTES = 512 * 1024 * 1024


def _boottime_seconds() -> float:
    """Return a process-independent monotonic clock that includes suspend."""
    return time.clock_gettime(time.CLOCK_BOOTTIME)


class PacketCaptureCoordinator:
    """Own one packet-capture generation and its mandatory safety timeout."""

    def __init__(
        self,
        max_seconds: float,
        notify: Callable[[str | None], None],
        stop_attempt_seconds: float = PACKET_CAPTURE_STOP_ATTEMPT_SECONDS,
        recovery_path: Path | None = None,
        deadline_clock: Callable[[], float] = _boottime_seconds,
    ) -> None:
        self._max_seconds = max(0.01, float(max_seconds))
        self._stop_attempt_seconds = max(0.01, float(stop_attempt_seconds))
        self._stop_retry_seconds = min(1.0, self._stop_attempt_seconds)
        self._notify = notify
        self._journal = PacketCaptureRecoveryJournal(recovery_path)
        self._deadline_clock = deadline_clock
        self.active = False
        self.watchdog_task: asyncio.Task | None = None
        self._generation = 0
        self._connection: Any = None
        self._deadline: float | None = None
        self._stop_lock = asyncio.Lock()

    def has_pending_recovery(self) -> bool:
        """Return whether startup owns a durable capture-recovery record."""
        return self._journal.exists()

    async def recover(self, connector: Any) -> None:
        """Reacquire and supervise an unconfirmed capture from an older process."""
        deadline = self._journal.load_deadline()
        if deadline is None:
            return
        state_name = type(connector.current_state).__name__.lower()
        if state_name in {"disconnected", "devicedisconnected"}:
            self._journal.clear()
            return
        connection = connector.current_connection
        if connection is None:
            raise UserVisibleRuntimeError(
                "Proton could not reacquire an unconfirmed packet capture; "
                "the backend will retry"
            )

        self._generation += 1
        generation = self._generation
        self.active = True
        self._connection = connection
        self._deadline = deadline
        self._arm_watchdog(generation, connection, deadline)
        stopped = await self._stop_generation(
            generation,
            connection,
            attempts=3,
            failure_message=(
                "A packet capture from the previous backend is still "
                "completion-unknown; safety retries remain active"
            ),
            completion_message="Recovered and stopped an unconfirmed packet capture",
            raise_on_failure=False,
        )
        if not stopped and (
            self.watchdog_task is None or self.watchdog_task.done()
        ):
            self._arm_watchdog(generation, connection, deadline)

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
        except Exception:
            # Core has not received a start request, so rejecting the selected
            # destination must leave the lifecycle completely retryable.
            raise UserVisibleRuntimeError(
                "Proton could not configure packet capture"
            ) from None
        deadline = self._deadline_clock() + self._max_seconds
        self._journal.store_deadline(deadline)
        self._generation += 1
        generation = self._generation
        self.active = True
        self._connection = connection
        self._deadline = deadline
        self.cancel_watchdog()
        try:
            async with asyncio.timeout(self._max_seconds):
                await connection.start_packet_capture()
        except asyncio.CancelledError:
            await self._compensate_unconfirmed_start(
                generation, connection, deadline
            )
            raise
        except Exception:
            await self._compensate_unconfirmed_start(
                generation, connection, deadline
            )
            raise UserVisibleRuntimeError(
                "Proton could not start packet capture"
            ) from None
        self._arm_watchdog(generation, connection, deadline)
        self._notify(None)

    async def stop(self) -> None:
        if not self.active:
            self.cancel_watchdog()
            return
        await self._stop_generation(
            self._generation,
            self._connection,
            attempts=1,
            failure_message=None,
            completion_message=None,
            raise_on_failure=True,
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
        self._journal.clear()
        self.active = False
        self._connection = None
        self._deadline = None
        self._generation += 1
        self.cancel_watchdog()

    def release_for_shutdown(self) -> None:
        """Release process-local work only after recovery ownership is durable."""
        if self.active:
            persisted_deadline = self._journal.load_deadline()
            if persisted_deadline is None:
                if self._deadline is None:
                    raise UserVisibleRuntimeError(
                        "Packet-capture recovery ownership could not be confirmed"
                    )
                self._journal.store_deadline(self._deadline)
        self.cancel_watchdog()

    @staticmethod
    def connection_supports_capture(connection: Any) -> bool:
        try:
            return bool(connection.supports_packet_capture())
        except (AttributeError, TypeError):
            return False

    def _arm_watchdog(
        self, generation: int, connection: Any, deadline: float
    ) -> None:
        self.cancel_watchdog()
        self.watchdog_task = asyncio.create_task(
            self._watchdog(generation, connection, deadline)
        )

    async def _compensate_unconfirmed_start(
        self, generation: int, connection: Any, deadline: float
    ) -> None:
        # Arm before calling Core again: even a second cancellation leaves the
        # original capture deadline represented by an independent task.
        self._arm_watchdog(generation, connection, deadline)
        stopped = await self._stop_generation(
            generation,
            connection,
            attempts=3,
            failure_message=(
                "Packet capture start could not be confirmed and Proton Core "
                "could not stop it"
            ),
            completion_message=None,
            raise_on_failure=False,
        )
        if (
            not stopped
            and generation == self._generation
            and self.active
            and (self.watchdog_task is None or self.watchdog_task.done())
        ):
            self._arm_watchdog(generation, connection, deadline)

    async def _watchdog(
        self, generation: int, connection: Any, deadline: float
    ) -> None:
        try:
            # asyncio's ordinary monotonic timer excludes suspend on Linux.
            # Rechecking CLOCK_BOOTTIME in short, idle chunks keeps the safety
            # deadline wall-time bounded across workstation sleep.
            while True:
                remaining = deadline - self._deadline_clock()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(remaining, 1.0))
            failure_message: str | None = (
                "Packet capture reached its time limit but Proton Core could "
                "not stop it; safety retries remain active"
            )
            while generation == self._generation and self.active:
                stopped = await self._stop_generation(
                    generation,
                    connection,
                    attempts=3,
                    failure_message=failure_message,
                    completion_message=(
                        "Packet capture stopped at the 15-minute safety limit"
                    ),
                    raise_on_failure=False,
                )
                if stopped:
                    return
                failure_message = None
                await asyncio.sleep(self._stop_retry_seconds)
        except asyncio.CancelledError:
            return

    async def _stop_generation(
        self,
        generation: int,
        connection: Any,
        *,
        attempts: int,
        failure_message: str | None,
        completion_message: str | None,
        raise_on_failure: bool,
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
                    if connection is None:
                        raise RuntimeError("capture connection is unavailable")
                    async with asyncio.timeout(self._stop_attempt_seconds):
                        await connection.stop_packet_capture()
                    break
                except Exception:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(self._stop_retry_seconds)
                        continue
                    if failure_message is not None:
                        self._notify(failure_message)
                    if not raise_on_failure:
                        return False
                    raise UserVisibleRuntimeError(
                        "Proton could not stop packet capture"
                    ) from None

            if generation != self._generation or connection is not self._connection:
                return False
            self.finish()
            self._notify(completion_message)
            return True
