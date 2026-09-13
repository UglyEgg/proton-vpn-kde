# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Task-bound reentrant ownership shared by independent lifecycle domains."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import Any, TypeVar


Result = TypeVar("Result")


class ScopeAdmissionExpired(TimeoutError):
    """The requested scope was not acquired before its owner's deadline."""


class TaskScope:
    """Serialize a domain; inheritance of asyncio context grants no authority.

    Only the owning task and explicitly delegated tasks may reenter. Delegation
    is tied to one acquisition, so an old child cannot enter a successor's scope.
    Authentication and connection use separate instances, in that lock order.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._owner: asyncio.Task[Any] | None = None
        self._token: object | None = None
        self._delegates: dict[asyncio.Task[Any], object] = {}

    def owned_by_current_task(self) -> bool:
        task = asyncio.current_task()
        return task is not None and self._token is not None and (
            task is self._owner or self._delegates.get(task) is self._token
        )

    @asynccontextmanager
    async def enter(self, *, deadline: float | None = None) -> AsyncIterator[None]:
        if deadline is not None and asyncio.get_running_loop().time() >= deadline:
            raise ScopeAdmissionExpired("Lifecycle ownership deadline expired")
        if self.owned_by_current_task():
            yield
            return
        if deadline is None:
            await self._lock.acquire()
        else:
            try:
                async with asyncio.timeout_at(deadline):
                    await self._lock.acquire()
            except TimeoutError:
                raise ScopeAdmissionExpired("Lifecycle ownership deadline expired") from None
        try:
            self._owner = asyncio.current_task()
            self._token = object()
            try:
                yield
            finally:
                self._owner = None
                self._token = None
        finally:
            self._lock.release()


def create_owned_task(
    coroutine: Coroutine[Any, Any, Result], *scopes: TaskScope
) -> asyncio.Task[Result]:
    """Delegate only explicitly held scopes before any child code can run."""
    if not scopes or any(not scope.owned_by_current_task() for scope in scopes):
        coroutine.close()
        raise RuntimeError(
            "Owned child task requested a lifecycle transition it does not own"
        )
    gate = asyncio.get_running_loop().create_future()
    started = False

    async def invoke() -> Result:
        nonlocal started
        await gate
        started = True
        return await coroutine

    pending = invoke()
    try:
        task = asyncio.create_task(pending)
    except BaseException:
        pending.close()
        coroutine.close()
        raise
    for scope in scopes:
        assert scope._token is not None
        scope._delegates[task] = scope._token

    def finished(child: asyncio.Task[Result]) -> None:
        for scope in scopes:
            scope._delegates.pop(child, None)
        if not started:
            coroutine.close()

    task.add_done_callback(finished)
    gate.set_result(None)
    return task
