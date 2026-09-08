# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Small asyncio helpers for provider calls with external user interaction."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
import threading
from typing import Generic, TypeVar, cast


Result = TypeVar("Result")


@dataclass(frozen=True, slots=True)
class OwnedOutcome(Generic[Result]):
    """A joined provider result, separate from the caller's cancellation."""

    value: Result | None
    error: Exception | asyncio.CancelledError | None
    caller_cancelled: bool
    cancellation_error: Exception | asyncio.CancelledError | None = None

    def result(self) -> Result:
        if self.caller_cancelled:
            raise asyncio.CancelledError
        if self.error is not None:
            raise self.error
        return cast(Result, self.value)


async def join_owned(
    operation: Awaitable[Result],
    *,
    cancel_operation: Callable[[], None] | None = None,
) -> OwnedOutcome[Result]:
    """Observe terminal provider work without losing cancellation precedence.

    A cancellation request (including a failing cancellation callback) is not
    proof the provider stopped. Join first, retaining both outcomes for the
    lifecycle owner to reconcile. This helper supplies no provider deadline.
    """
    task = asyncio.ensure_future(operation)
    caller_cancelled = False
    cancellation_error: Exception | asyncio.CancelledError | None = None
    while not task.done():
        try:
            # wait() does not propagate cancellation to its input tasks. Unlike
            # a repeatedly cancelled shield, it also does not install detached
            # exception-reporting callbacks on the provider (Python 3.14).
            await asyncio.wait({task})
        except asyncio.CancelledError:
            first_cancellation = not caller_cancelled
            caller_cancelled = True
            if first_cancellation and cancel_operation is not None:
                try:
                    cancel_operation()
                except (Exception, asyncio.CancelledError) as error:
                    cancellation_error = error

    try:
        value = task.result()
    except (Exception, asyncio.CancelledError) as error:
        return OwnedOutcome(None, error, caller_cancelled, cancellation_error)
    return OwnedOutcome(value, None, caller_cancelled, cancellation_error)


async def await_owned(
    operation: Awaitable[Result],
    *,
    cancel_operation: Callable[[], None] | None = None,
) -> Result:
    """Join accepted work, then propagate the caller's terminal outcome."""
    return (await join_owned(operation, cancel_operation=cancel_operation)).result()


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
