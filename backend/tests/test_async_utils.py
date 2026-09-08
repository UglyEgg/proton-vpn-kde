# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import threading
import unittest

from proton_vpn_kde_backend.async_utils import (
    await_owned,
    join_owned,
    run_in_daemon_thread,
)


class OwnedOperationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        loop = asyncio.get_event_loop()
        previous = loop.get_exception_handler()
        self.unhandled = []
        loop.set_exception_handler(lambda _loop, context: self.unhandled.append(context))
        self.addCleanup(loop.set_exception_handler, previous)

    async def asyncTearDown(self):
        await asyncio.sleep(0)
        self.assertEqual([], self.unhandled)

    async def test_terminal_outcome_matrix(self):
        for cancel_caller in (False, True):
            for terminal in ("success", "failure", "cancelled"):
                with self.subTest(cancel_caller=cancel_caller, terminal=terminal):
                    child = asyncio.get_running_loop().create_future()
                    cancellation_requests = []
                    owner = asyncio.create_task(join_owned(
                        child,
                        cancel_operation=lambda requests=cancellation_requests: requests.append(1),
                    ))
                    await asyncio.sleep(0)
                    if cancel_caller:
                        owner.cancel()
                        await asyncio.sleep(0)
                        owner.cancel()
                        await asyncio.sleep(0)
                        self.assertFalse(owner.done())
                        self.assertFalse(child.cancelled())
                    if terminal == "success":
                        child.set_result("provider result")
                    elif terminal == "failure":
                        child.set_exception(ValueError("provider failed"))
                    else:
                        child.cancel()
                    outcome = await owner
                    self.assertEqual(cancel_caller, outcome.caller_cancelled)
                    self.assertEqual([1] if cancel_caller else [], cancellation_requests)
                    if cancel_caller or terminal == "cancelled":
                        with self.assertRaises(asyncio.CancelledError):
                            outcome.result()
                    elif terminal == "failure":
                        with self.assertRaises(ValueError):
                            outcome.result()
                    else:
                        self.assertEqual("provider result", outcome.result())
                    if terminal == "failure":
                        self.assertIsInstance(outcome.error, ValueError)

    async def test_cancellation_callback_failure_does_not_detach_provider(self):
        for error_type in (ValueError, asyncio.CancelledError):
            with self.subTest(error=error_type):
                child = asyncio.get_running_loop().create_future()

                def cancel(failure=error_type):
                    raise failure()

                owner = asyncio.create_task(join_owned(child, cancel_operation=cancel))
                await asyncio.sleep(0)
                owner.cancel()
                await asyncio.sleep(0)
                self.assertFalse(owner.done())
                child.set_result("done")
                outcome = await owner
                self.assertIsInstance(outcome.cancellation_error, error_type)
                self.assertEqual("done", outcome.value)
                with self.assertRaises(asyncio.CancelledError):
                    outcome.result()

    async def test_convenience_wrapper_preserves_cancellation_after_child_failure(self):
        child = asyncio.get_running_loop().create_future()
        owner = asyncio.create_task(await_owned(child))
        await asyncio.sleep(0)
        owner.cancel()
        await asyncio.sleep(0)
        child.set_exception(ValueError("late provider failure"))
        with self.assertRaises(asyncio.CancelledError):
            await owner

    async def test_already_terminal_provider_is_observed(self):
        child = asyncio.get_running_loop().create_future()
        child.set_result(42)
        self.assertEqual(42, await await_owned(child))


class DaemonThreadTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_does_not_wait_for_provider_prompt(self):
        started = threading.Event()
        released = threading.Event()

        def blocking_prompt():
            self.assertTrue(threading.current_thread().daemon)
            started.set()
            released.wait(timeout=2)
            return True

        task = asyncio.create_task(run_in_daemon_thread(blocking_prompt))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.005)
            self.assertTrue(started.is_set())

            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=0.1)
        finally:
            released.set()
