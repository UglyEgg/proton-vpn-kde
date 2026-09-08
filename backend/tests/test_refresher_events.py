# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Provider-free tests of bounded callback work and account ownership."""

import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
import weakref

from core_fakes import core_module_fakes
import test_proton_core_adapter as adapter_tests
from proton_vpn_kde_backend.adapters import (
    BACKGROUND_REFRESH_DEGRADED_MESSAGE, ProtonCoreAdapter,
)
from proton_vpn_kde_backend.refresher_events import (
    RefreshFailureKind, RefresherFailureRelay, ignore_retired_refresh_error,
)


class ProtonAPIAuthenticationNeeded(Exception):
    pass


async def drain(relay):
    while relay.task is not None:
        await asyncio.wait_for(asyncio.shield(relay.task), timeout=1)
        await asyncio.sleep(0)  # Run the task's retirement callback.


class RefresherFailureRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_callback_defers_coalesces_and_prioritizes_expiry(self):
        handler = AsyncMock()
        relay = RefresherFailureRelay(handler, Mock())
        callback = relay.bind(8)
        for _ in range(1000):
            callback(ValueError("not retained"))
        callback(ProtonAPIAuthenticationNeeded())
        callback(RuntimeError())
        handler.assert_not_awaited()
        worker = relay.task
        await drain(relay)
        handler.assert_awaited_once()
        failure = handler.await_args.args[0]
        self.assertEqual(8, failure.epoch)
        self.assertEqual(RefreshFailureKind.AUTHENTICATION, failure.kind)
        self.assertTrue(worker.done())
        self.assertIsNone(relay.task)

    async def test_exception_and_traceback_are_not_retained(self):
        class ProviderError(Exception):
            pass
        relay = RefresherFailureRelay(AsyncMock(), Mock())
        callback = relay.bind(0)
        def report_from_provider():
            try:
                raise ProviderError("must not reach a snapshot or log")
            except ProviderError as error:
                reference = weakref.ref(error)
                callback(error)
            return reference
        reference = report_from_provider()
        self.assertIsNone(reference())
        await drain(relay)

    async def test_invalidation_drops_old_queued_and_late_callbacks(self):
        handler = AsyncMock()
        relay = RefresherFailureRelay(handler, Mock())
        old = relay.bind(0)
        old(ProtonAPIAuthenticationNeeded())
        current = relay.bind(1)
        old(ProtonAPIAuthenticationNeeded())
        current(RuntimeError())
        await drain(relay)
        handler.assert_awaited_once()
        self.assertEqual(1, handler.await_args.args[0].epoch)
        self.assertEqual(RefreshFailureKind.UPDATE, handler.await_args.args[0].kind)

    async def test_one_active_worker_retains_one_successor_notice(self):
        entered, release = asyncio.Event(), asyncio.Event()
        received = []
        async def handler(failure):
            received.append(failure)
            entered.set()
            await release.wait()
        relay = RefresherFailureRelay(handler, Mock())
        callback = relay.bind(1)
        callback(RuntimeError())
        await entered.wait()
        worker = relay.task
        for _ in range(1000):
            callback(RuntimeError())
        callback(ProtonAPIAuthenticationNeeded())
        self.assertIs(worker, relay.task)
        release.set()
        await drain(relay)
        self.assertEqual([RefreshFailureKind.UPDATE, RefreshFailureKind.AUTHENTICATION],
                         [failure.kind for failure in received])

    async def test_notice_between_task_return_and_retirement_is_not_stranded(self):
        received = []
        callback = None
        async def handler(failure):
            received.append(failure)
            if len(received) == 1:
                asyncio.get_running_loop().call_soon(callback, RuntimeError())
        relay = RefresherFailureRelay(handler, Mock())
        callback = relay.bind(0)
        callback(RuntimeError())
        await drain(relay)
        self.assertEqual(2, len(received))

    async def test_stop_rejects_future_work_but_retains_running_handler(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(_failure):
            entered.set()
            await release.wait()
        handler_mock = AsyncMock(side_effect=handler)
        relay = RefresherFailureRelay(handler_mock, Mock())
        callback = relay.bind(0)
        callback(RuntimeError())
        await entered.wait()
        worker = relay.task
        relay.stop()
        callback(ProtonAPIAuthenticationNeeded())
        self.assertFalse(worker.done())
        release.set()
        await drain(relay)
        handler_mock.assert_awaited_once()
        with self.assertRaises(RuntimeError):
            relay.bind(1)

    async def test_handler_error_has_owned_safe_failure_outcome(self):
        failed = Mock()
        relay = RefresherFailureRelay(
            AsyncMock(side_effect=RuntimeError("private provider details")), failed
        )
        with self.assertLogs("proton_vpn_kde_backend.refresher_events", level="ERROR") as logs:
            relay.bind(4)(RuntimeError("also private"))
            await drain(relay)
        failed.assert_called_once()
        self.assertEqual(4, failed.call_args.args[0].epoch)
        self.assertNotIn("private", " ".join(logs.output))

    @unittest.skipUnless(hasattr(asyncio, "eager_task_factory"), "Python 3.12+ eager tasks")
    async def test_eager_factory_still_returns_before_handler_runs(self):
        loop = asyncio.get_running_loop()
        original = loop.get_task_factory()
        loop.set_task_factory(asyncio.eager_task_factory)
        try:
            await self.test_callback_defers_coalesces_and_prioritizes_expiry()
        finally:
            loop.set_task_factory(original)


@patch.dict("sys.modules", core_module_fakes())
class AdapterRefresherErrorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        environment = patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.api, self.connector = adapter_tests.ProtonCoreAdapterTests().make_api()
        self.snapshots = []
        self.adapter = ProtonCoreAdapter(
            self.api, account_transition_path=Path(directory.name) / "account.json"
        )

    def callback(self):
        return self.api.refresher.set_error_callback.call_args.args[0]

    async def test_background_expiry_preserves_established_tunnel(self):
        self.connector.current_state = adapter_tests.state_named("Connected")
        initial = await self.adapter.initialize(self.snapshots.append)
        callback = self.callback()
        callback(ProtonAPIAuthenticationNeeded("private"))
        self.assertTrue(initial.logged_in)
        self.assertFalse(self.snapshots)
        await drain(self.adapter._refresher_errors)
        self.assertFalse(self.snapshots[-1].logged_in)
        self.assertEqual("expired", self.snapshots[-1].auth_state)
        self.assertEqual("connected", self.snapshots[-1].state)
        self.connector.disconnect.assert_not_awaited()
        self.api.logout.assert_not_awaited()
        self.api.refresher.disable.assert_awaited_once()
        self.assertFalse(self.adapter._reconnector.enabled)
        await self.adapter.close()

    async def test_non_auth_failure_is_persistent_degraded_not_expiry(self):
        self.connector.current_state = adapter_tests.state_named("Connected")
        await self.adapter.initialize(self.snapshots.append)
        self.callback()(RuntimeError("private"))
        await drain(self.adapter._refresher_errors)
        snapshot = self.snapshots[-1]
        self.assertTrue(snapshot.logged_in)
        self.assertEqual("signed_in_degraded", snapshot.auth_state)
        self.assertEqual("connected", snapshot.state)
        self.assertEqual(BACKGROUND_REFRESH_DEGRADED_MESSAGE, snapshot.message)
        self.api.refresher.disable.assert_not_awaited()
        self.assertTrue(self.adapter._reconnector.enabled)
        self.adapter._status_message = ""
        self.adapter.status_update(self.connector.current_state)
        self.assertEqual(snapshot.message, self.snapshots[-1].message)
        self.connector.disconnect.assert_not_awaited()
        await self.adapter.close()

    async def test_background_expiry_retires_pending_manual_lookup(self):
        entered = asyncio.Event()
        async def lookup():
            entered.set()
            await asyncio.Event().wait()
        self.api.refresher.get_up_to_date_server_list.side_effect = lookup
        await self.adapter.initialize(self.snapshots.append)
        connection = asyncio.create_task(self.adapter.connect_fastest())
        await entered.wait()
        self.callback()(ProtonAPIAuthenticationNeeded())
        await drain(self.adapter._refresher_errors)
        with self.assertRaises(asyncio.CancelledError):
            await connection
        self.assertEqual("expired", self.snapshots[-1].auth_state)
        self.assertFalse(self.adapter._manual_connection_tasks)
        self.api.refresher.disable.assert_awaited_once()
        self.connector.connect.assert_not_awaited()
        await self.adapter.close()

    async def test_unexpected_handler_failure_publishes_safe_recovery_state(self):
        await self.adapter.initialize(self.snapshots.append)
        with (
            patch.object(self.adapter, "_expire_session",
                         new=AsyncMock(side_effect=RuntimeError("private details"))),
            self.assertLogs("proton_vpn_kde_backend.refresher_events", level="ERROR") as logs,
        ):
            self.callback()(ProtonAPIAuthenticationNeeded("also private"))
            await drain(self.adapter._refresher_errors)
        self.assertEqual("authentication_unknown", self.snapshots[-1].auth_state)
        self.assertFalse(self.snapshots[-1].logged_in)
        self.assertNotIn("private", self.snapshots[-1].message + " ".join(logs.output))
        await self.adapter.close()

    async def test_queued_error_rechecks_epoch_after_authentication_lock(self):
        await self.adapter.initialize(self.snapshots.append)
        async with self.adapter._serialized_authentication_transition():
            self.callback()(ProtonAPIAuthenticationNeeded())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.adapter._authentication_epoch += 1
        before = list(self.snapshots)
        await drain(self.adapter._refresher_errors)
        self.assertEqual(before, self.snapshots)
        self.api.refresher.disable.assert_not_awaited()
        await self.adapter.close()

    async def test_late_callback_cannot_overwrite_logout(self):
        await self.adapter.initialize(self.snapshots.append)
        callback = self.callback()
        self.callback()(RuntimeError())
        await self.adapter.logout()
        callback(ProtonAPIAuthenticationNeeded())
        await drain(self.adapter._refresher_errors)
        self.assertEqual("account_restart_required", self.snapshots[-1].auth_state)
        self.assertFalse(self.snapshots[-1].logged_in)
        self.api.refresher.disable.assert_awaited_once()
        await self.adapter.close()

    async def test_callback_is_installed_before_enable_and_init_does_not_erase_failure(self):
        async def enable():
            self.callback()(ProtonAPIAuthenticationNeeded())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        self.api.refresher.enable.side_effect = enable
        await self.adapter.initialize(self.snapshots.append)
        await drain(self.adapter._refresher_errors)
        self.assertFalse(self.snapshots[-1].logged_in)
        self.assertEqual("expired", self.snapshots[-1].auth_state)
        await self.adapter.close()

    async def test_login_commit_does_not_erase_early_refresher_failure(self):
        self.api.is_user_logged_in.return_value = False
        self.api.login.return_value = type(
            "Login", (), {"authenticated": True, "twofa_required": False}
        )()
        await self.adapter.initialize(self.snapshots.append)
        async def enable():
            self.callback()(ProtonAPIAuthenticationNeeded())
            await asyncio.sleep(0)
        self.api.refresher.enable.side_effect = enable
        await self.adapter.login("unused", "unused")
        await drain(self.adapter._refresher_errors)
        self.assertFalse(self.snapshots[-1].logged_in)
        self.assertEqual("expired", self.snapshots[-1].auth_state)
        await self.adapter.close()

    async def test_close_fences_queued_error_before_acquiring_authentication_lock(self):
        await self.adapter.initialize(self.snapshots.append)
        async with self.adapter._serialized_authentication_transition():
            callback = self.callback()
            callback(ProtonAPIAuthenticationNeeded())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            close = asyncio.create_task(self.adapter.close())
            await asyncio.sleep(0)
            self.assertFalse(close.done())
        await asyncio.wait_for(close, 1)
        callback(ProtonAPIAuthenticationNeeded())
        await drain(self.adapter._refresher_errors)
        self.assertTrue(self.adapter._logged_in)
        self.api.refresher.set_error_callback.assert_called_with(ignore_retired_refresh_error)
        self.callback()(RuntimeError("late provider error"))
        self.assertIsNone(self.adapter._refresher_errors.task)

    async def test_cancelled_close_waiter_still_joins_accepted_error_cleanup(self):
        entered, release = asyncio.Event(), asyncio.Event()
        await self.adapter.initialize(self.snapshots.append)
        async def disable():
            entered.set()
            await release.wait()
        self.api.refresher.disable.side_effect = disable
        self.callback()(ProtonAPIAuthenticationNeeded())
        await entered.wait()
        close = asyncio.create_task(self.adapter.close())
        await asyncio.sleep(0)
        close.cancel()
        await asyncio.sleep(0)
        self.assertFalse(close.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(close, 1)
        await drain(self.adapter._refresher_errors)
        await self.adapter.close()

    async def test_close_deadline_rejects_unretired_background_handler(self):
        entered, release = asyncio.Event(), asyncio.Event()
        await self.adapter.initialize(self.snapshots.append)
        async def disable():
            entered.set()
            await release.wait()
        self.api.refresher.disable.side_effect = disable
        self.callback()(ProtonAPIAuthenticationNeeded())
        await entered.wait()
        self.adapter._connection_retirement_seconds = 0.01
        self.adapter._terminal_exit = Mock(side_effect=RuntimeError("terminal exit"))
        try:
            with self.assertRaisesRegex(TimeoutError, "shutdown deadline"):
                await self.adapter.close()
            self.adapter._terminal_exit.assert_not_called()
        finally:
            release.set()
            await drain(self.adapter._refresher_errors)
        # The enclosing service must retire the process after this failure;
        # late handler completion cannot turn it into a successful close.
        with self.assertRaises(TimeoutError):
            await self.adapter.close()
