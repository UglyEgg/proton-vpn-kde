# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import inspect
import unittest
from unittest.mock import patch

from proton_vpn_kde_backend.task_scope import ScopeAdmissionExpired, TaskScope, create_owned_task


class TaskScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_deadline_cannot_acquire_a_sibling_scope_late(self):
        scope = TaskScope()
        entered = []

        async def sibling():
            async with scope.enter(deadline=asyncio.get_running_loop().time() + 0.01):
                entered.append("late")

        async with scope.enter():
            child = asyncio.create_task(sibling())
            with self.assertRaises(ScopeAdmissionExpired):
                await child
            self.assertTrue(scope.owned_by_current_task())
        self.assertEqual([], entered)
        async with scope.enter():
            self.assertTrue(scope.owned_by_current_task())

    async def test_expired_deadline_rejects_even_reentrant_admission(self):
        scope = TaskScope()
        async with scope.enter():
            with self.assertRaises(ScopeAdmissionExpired):
                async with scope.enter(deadline=asyncio.get_running_loop().time() - 1):
                    self.fail("expired scope entered")
            self.assertTrue(scope.owned_by_current_task())
        self.assertFalse(scope.owned_by_current_task())

    async def test_admission_deadline_does_not_cancel_the_owned_body(self):
        scope = TaskScope()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 0.01
        release = asyncio.Event()
        async with scope.enter(deadline=deadline):
            timer = loop.call_at(deadline + 0.01, release.set)
            try:
                await release.wait()
                self.assertTrue(scope.owned_by_current_task())
            finally:
                timer.cancel()

    async def test_delegation_does_not_authorize_siblings(self):
        scope = TaskScope()
        entered = []

        async def child(name):
            async with scope.enter():
                entered.append(name)

        async with scope.enter():
            async with scope.enter():
                delegated = create_owned_task(child("delegated"), scope)
                sibling = asyncio.create_task(child("sibling"))
                await delegated
                self.assertEqual(["delegated"], entered)
        await sibling
        self.assertEqual(["delegated", "sibling"], entered)

    async def test_expired_delegation_cannot_reenter_a_successor(self):
        scope = TaskScope()
        release = asyncio.Event()
        entered = asyncio.Event()

        async def child():
            await release.wait()
            async with scope.enter():
                entered.set()

        async with scope.enter():
            delegated = create_owned_task(child(), scope)
            await asyncio.sleep(0)
        async with scope.enter():
            release.set()
            await asyncio.sleep(0)
            self.assertFalse(entered.is_set())
        await delegated
        self.assertTrue(entered.is_set())

    async def test_unowned_delegation_closes_the_unstarted_coroutine(self):
        async def child():
            self.fail("not authorized")

        coroutine = child()
        with self.assertRaises(RuntimeError):
            create_owned_task(coroutine, TaskScope())
        self.assertEqual(inspect.CORO_CLOSED, inspect.getcoroutinestate(coroutine))

    async def test_cancel_before_first_execution_closes_child(self):
        scope = TaskScope()

        async def child():
            self.fail("cancelled before execution")

        coroutine = child()
        async with scope.enter():
            task = create_owned_task(coroutine, scope)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(inspect.CORO_CLOSED, inspect.getcoroutinestate(coroutine))

    async def test_task_creation_failure_closes_child(self):
        scope = TaskScope()

        async def child():
            self.fail("task creation failed")

        coroutine = child()
        async with scope.enter():
            with patch(
                "proton_vpn_kde_backend.task_scope.asyncio.create_task",
                side_effect=RuntimeError("task factory failed"),
            ):
                with self.assertRaises(RuntimeError):
                    create_owned_task(coroutine, scope)
        self.assertEqual(inspect.CORO_CLOSED, inspect.getcoroutinestate(coroutine))

    @unittest.skipUnless(hasattr(asyncio, "eager_task_factory"), "Python 3.12+")
    async def test_eager_task_factory_cannot_run_before_delegation(self):
        scope = TaskScope()
        loop = asyncio.get_running_loop()
        previous = loop.get_task_factory()

        async def child():
            async with scope.enter():
                return scope.owned_by_current_task()

        try:
            loop.set_task_factory(asyncio.eager_task_factory)
            async with scope.enter():
                self.assertTrue(await create_owned_task(child(), scope))
        finally:
            loop.set_task_factory(previous)
