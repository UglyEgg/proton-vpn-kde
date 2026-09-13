# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bounded, session-tagged handoff from Core's synchronous error callback."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum, auto
import logging

from .errors import is_proton_authentication_needed


logger = logging.getLogger(__name__)


def ignore_retired_refresh_error(_error: Exception) -> None:
    """Sink late Core notices after adapter retirement without retaining it.

    Setting Core's callback to None makes it re-raise provider exceptions into
    the event loop. Public disable does not prove every refresh child joined.
    """


class RefreshFailureKind(Enum):
    UPDATE = auto()
    AUTHENTICATION = auto()


@dataclass(frozen=True, slots=True)
class RefreshFailure:
    epoch: int
    generation: int
    kind: RefreshFailureKind


class RefresherFailureRelay:
    """Own at most one worker and one coalesced notice, never an exception.

    This owns our callback work, not Core's refresh children. Invalidation
    drops queued notices; an already-running handler must recheck its session
    after acquiring lifecycle authority. Shutdown joins that handler.
    """

    def __init__(
        self,
        handler: Callable[[RefreshFailure], Awaitable[None]],
        failed: Callable[[RefreshFailure], None],
    ) -> None:
        self._handler = handler
        self._failed = failed
        self._generation = 0
        self._closed = False
        self._pending: RefreshFailure | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def task(self) -> asyncio.Task[None] | None:
        return self._task

    def is_current(self, failure: RefreshFailure) -> bool:
        return not self._closed and failure.generation == self._generation

    def invalidate(self) -> None:
        self._generation += 1
        self._pending = None

    def stop(self) -> None:
        self._closed = True
        self.invalidate()

    def bind(self, epoch: int) -> Callable[[Exception], None]:
        if self._closed:
            raise RuntimeError("The background error relay is closed")
        self.invalidate()
        generation = self._generation

        def report(error: Exception) -> None:
            if self._closed or generation != self._generation:
                return
            # Do not retain provider tracebacks, messages or account data.
            kind = (
                RefreshFailureKind.AUTHENTICATION
                if is_proton_authentication_needed(error)
                else RefreshFailureKind.UPDATE
            )
            if self._pending is None or kind is RefreshFailureKind.AUTHENTICATION:
                self._pending = RefreshFailure(epoch, generation, kind)
            if self._task is None:
                self._task = asyncio.create_task(self._drain())
                self._task.add_done_callback(self._finished)

        return report

    async def _drain(self) -> None:
        # Even an eager task factory must return to the provider callback
        # before a handler can stop/join its scheduler.
        await asyncio.sleep(0)
        while self._pending is not None:
            failure, self._pending = self._pending, None
            if not self.is_current(failure):
                continue
            try:
                await self._handler(failure)
            except Exception:
                logger.error("Background refresh-error reconciliation failed")
                self._failed(failure)

    def _finished(self, task: asyncio.Task[None]) -> None:
        # Retirement owns any currently running handler. No task exception is
        # abandoned even when its frontend or original callback has gone.
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error("Background refresh-error worker failed")
        if self._task is task:
            self._task = None
            # A callback may have arrived between terminal return and this
            # done callback. Transfer its retained notice to one successor.
            if self._pending is not None and not self._closed:
                self._task = asyncio.create_task(self._drain())
                self._task.add_done_callback(self._finished)
