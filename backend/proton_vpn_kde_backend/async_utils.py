# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Small asyncio helpers for provider calls with external user interaction."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import threading
from typing import TypeVar


Result = TypeVar("Result")


async def await_owned(
    operation: Awaitable[Result],
    *,
    cancel_operation: Callable[[], None] | None = None,
) -> Result:
    """Retain ownership of an operation until it has actually stopped.

    Shielding prevents cancellation of the caller from silently detaching the
    child.  If the caller is cancelled, request provider-specific cancellation
    once and continue joining the child before propagating cancellation.
    """

    task = asyncio.ensure_future(operation)
    caller_cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            caller = asyncio.current_task()
            if task.cancelled() and (
                caller is None or caller.cancelling() == 0
            ):
                break
            if not caller_cancelled and cancel_operation is not None:
                cancel_operation()
            caller_cancelled = True

    if caller_cancelled:
        # Observe the child's terminal state, but preserve cancellation as the
        # result owned by the caller.
        try:
            task.result()
        except (Exception, asyncio.CancelledError):
            pass
        raise asyncio.CancelledError
    return task.result()


async def run_in_daemon_thread(operation: Callable[[], Result]) -> Result:
    """Run a blocking provider call without making process exit wait for it.

    Secret Service providers may keep a synchronous keyring call open while a
    desktop prompt is awaiting user input.  A daemon thread keeps that prompt
    away from the asyncio/D-Bus loop, while still allowing an abandoned backend
    activation to terminate after its frontend has disappeared.
    """

    loop = asyncio.get_running_loop()
    result: asyncio.Future[Result] = loop.create_future()

    def complete(value: Result | None, error: BaseException | None) -> None:
        if result.done():
            return
        if error is not None:
            result.set_exception(error)
        else:
            result.set_result(value)  # type: ignore[arg-type]

    def invoke() -> None:
        value: Result | None = None
        error: BaseException | None = None
        try:
            value = operation()
        except BaseException as caught:  # Preserve the provider's exception type.
            error = caught
        try:
            loop.call_soon_threadsafe(complete, value, error)
        except RuntimeError:
            # The owning process is already leaving after an abandoned prompt.
            pass

    threading.Thread(
        target=invoke,
        name="proton-vpn-secret-service",
        daemon=True,
    ).start()
    return await result
