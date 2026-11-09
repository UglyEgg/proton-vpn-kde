# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import os
from pathlib import Path
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core_fakes import core_module_fakes
import test_proton_core_adapter as adapter_tests
from proton_vpn_kde_backend.adapters import ProtonCoreAdapter
from proton_vpn_kde_backend.controller import BackendController
from proton_vpn_kde_backend.errors import SecretStoreUnavailableError, UserVisibleRuntimeError
from proton_vpn_kde_backend.reconnector import AsyncReconnector


class KeyringLocked(Exception):
    pass


class OwnedCoreAdmissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, {"XDG_RUNTIME_DIR": temporary}))
        self.api, self.connector = adapter_tests.ProtonCoreAdapterTests().make_api()
        self.factory = Mock(return_value=self.api)
        modules = core_module_fakes()
        api_module = ModuleType("proton.vpn.core.api")
        api_module.ProtonVPNAPI = self.factory
        holder_module = ModuleType("proton.vpn.core.session_holder")
        holder_module.ClientTypeMetadata = lambda **fields: SimpleNamespace(**fields)
        modules.update({"proton.vpn.core.api": api_module,
                        "proton.vpn.core.session_holder": holder_module})
        self.enterContext(patch.dict("sys.modules", modules))
        self.enterContext(patch.dict(os.environ, {"PROTON_LOADER_OVERRIDES": "keyring=legacy"}))
        self.adapter = ProtonCoreAdapter(account_transition_path=Path(temporary) / "account.json")
        self.snapshots = []
        self.waiter = self.enterContext(patch(
            "proton_vpn_kde_backend.adapters.wait_for_secret_service", new_callable=AsyncMock,
        ))
        self.addAsyncCleanup(self.adapter.close)
        self.addCleanup(self.api.logout.assert_not_awaited)
        self.addCleanup(self.connector.connect.assert_not_awaited)
        self.addCleanup(self.connector.disconnect.assert_not_awaited)

    async def test_cached_success_cannot_construct_core_before_store_admission(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def wait(_remaining, *, initial_admission):
            self.assertTrue(initial_admission)
            entered.set()
            await release.wait()
            return True
        self.waiter.side_effect = wait
        self.api.is_user_logged_in.return_value = True
        task = asyncio.create_task(self.adapter.initialize(self.snapshots.append))
        await asyncio.wait_for(entered.wait(), 1)
        self.factory.assert_not_called()
        self.api.is_user_logged_in.assert_not_called()
        self.api.get_vpn_connector.assert_not_awaited()
        self.assertFalse(self.snapshots[-1].ready)
        self.assertEqual("authentication_unknown", self.snapshots[-1].auth_state)
        self.assertEqual("keyring=secret_service", os.environ["PROTON_LOADER_OVERRIDES"])
        release.set()
        snapshot = await asyncio.wait_for(task, 1)
        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.logged_in)
        self.factory.assert_called_once()
        self.api.is_user_logged_in.assert_called_once()

    async def test_unavailable_store_never_constructs_core_or_claims_signout(self):
        self.waiter.return_value = False
        controller = BackendController(self.adapter)
        with self.assertLogs("proton_vpn_kde_backend.controller", level="ERROR"):
            self.assertFalse(await controller.start())
        self.factory.assert_not_called()
        self.api.is_user_logged_in.assert_not_called()
        self.assertEqual("authentication_unknown", controller.snapshot.auth_state)
        self.assertEqual("secret_store_locked", controller.snapshot.error_code)

    async def test_empty_admitted_store_can_publish_a_normal_signin_state(self):
        self.waiter.return_value = True
        self.api.is_user_logged_in.return_value = False
        snapshot = await self.adapter.initialize(self.snapshots.append)
        self.assertTrue(snapshot.ready)
        self.assertFalse(snapshot.logged_in)
        self.assertEqual("signed_out", snapshot.auth_state)
        self.factory.assert_called_once()

    async def test_cancelled_admission_does_not_start_core_later(self):
        entered = asyncio.Event()
        async def wait(_remaining, *, initial_admission):
            self.assertTrue(initial_admission)
            entered.set()
            await asyncio.Event().wait()
        self.waiter.side_effect = wait
        task = asyncio.create_task(self.adapter.initialize(self.snapshots.append))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.factory.assert_not_called()
        self.api.is_user_logged_in.assert_not_called()

    async def test_late_admission_cannot_start_a_new_credential_budget(self):
        self.waiter.return_value = True
        with patch("proton_vpn_kde_backend.adapters.SECRET_STORE_WAIT_SECONDS", 0):
            with self.assertRaises(SecretStoreUnavailableError):
                await self.adapter.initialize(self.snapshots.append)
        self.factory.assert_not_called()
        self.api.is_user_logged_in.assert_not_called()

    async def test_pending_cleanup_retains_its_short_admission_boundary(self):
        self.adapter._packet_capture.has_pending_recovery = Mock(return_value=True)
        self.waiter.return_value = False
        with self.assertRaises(UserVisibleRuntimeError):
            await self.adapter.initialize(self.snapshots.append)
        self.assertLessEqual(self.waiter.await_args.args[0], 5.0)
        self.assertTrue(self.adapter.has_pending_startup_recovery())
        self.factory.assert_not_called()

    async def test_admission_and_session_lookup_share_the_original_deadline(self):
        upper = []
        async def wait(remaining, *, initial_admission):
            self.assertTrue(initial_admission)
            upper.append(asyncio.get_running_loop().time() + remaining)
            await asyncio.sleep(0.01)
            return True
        self.waiter.side_effect = wait
        before = asyncio.get_running_loop().time()
        with patch.object(self.adapter, "_restore_saved_session",
                          wraps=self.adapter._restore_saved_session) as restore:
            await self.adapter.initialize(self.snapshots.append)
        deadline = restore.await_args.args[0]
        self.assertGreaterEqual(deadline, before + 120)
        self.assertLessEqual(deadline, upper[0])


@patch.dict("sys.modules", core_module_fakes())
class StartupCredentialRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, {"XDG_RUNTIME_DIR": temporary}))
        self.api, self.connector = adapter_tests.ProtonCoreAdapterTests().make_api()
        self.adapter = ProtonCoreAdapter(
            self.api, account_transition_path=Path(temporary) / "account.json"
        )
        self.snapshots = []
        def reconnector(*args, **kwargs):
            kwargs["session_probe"] = SimpleNamespace(
                is_unlocked=AsyncMock(return_value=True), close=AsyncMock(),
            )
            return AsyncReconnector(*args, **kwargs)
        self.enterContext(patch("proton_vpn_kde_backend.adapters.AsyncReconnector", new=reconnector))
        self.waiter = self.enterContext(patch(
            "proton_vpn_kde_backend.adapters.wait_for_secret_service", new_callable=AsyncMock,
        ))
        self.addAsyncCleanup(self.adapter.close)
        self.addCleanup(self.api.logout.assert_not_awaited)
        self.addCleanup(self.connector.connect.assert_not_awaited)
        self.addCleanup(self.connector.disconnect.assert_not_awaited)

    async def test_waits_for_unlock_then_restores_without_an_adapter_reset(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def wait(_timeout):
            entered.set()
            await release.wait()
            return True
        self.waiter.side_effect = wait
        self.api.is_user_logged_in.side_effect = [KeyringLocked("private"), True]
        task = asyncio.create_task(self.adapter.initialize(self.snapshots.append))
        await asyncio.wait_for(entered.wait(), 1)
        self.assertEqual(1, self.api.is_user_logged_in.call_count)
        self.api.get_vpn_connector.assert_not_awaited()
        self.assertFalse(self.snapshots[-1].ready)
        self.assertEqual("starting", self.snapshots[-1].state)
        self.assertIn("secret store", self.snapshots[-1].message)
        self.assertNotIn("private", self.snapshots[-1].message)
        release.set()
        snapshot = await asyncio.wait_for(task, 1)
        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.logged_in)
        self.assertEqual(2, self.api.is_user_logged_in.call_count)

    async def test_second_refusal_is_terminal_not_a_prompt_loop(self):
        self.api.is_user_logged_in.side_effect = KeyringLocked("private")
        self.waiter.return_value = True
        with self.assertRaises(SecretStoreUnavailableError):
            await self.adapter.initialize(self.snapshots.append)
        self.assertEqual(2, self.api.is_user_logged_in.call_count)
        self.waiter.assert_awaited_once()
        self.api.get_vpn_connector.assert_not_awaited()

    async def test_readiness_budget_exhaustion_keeps_credentials_unknown(self):
        self.api.is_user_logged_in.side_effect = KeyringLocked("private")
        self.waiter.return_value = False
        controller = BackendController(self.adapter)
        with self.assertLogs("proton_vpn_kde_backend.controller", level="ERROR") as logs:
            self.assertFalse(await controller.start())
        self.assertFalse(controller.snapshot.ready)
        self.assertEqual("authentication_unknown", controller.snapshot.auth_state)
        self.assertEqual("secret_store_locked", controller.snapshot.error_code)
        self.assertNotIn("private", str(logs.output))
        self.assertEqual(1, self.api.is_user_logged_in.call_count)
        self.api.get_vpn_connector.assert_not_awaited()

    async def test_timeout_does_not_launch_another_provider_worker(self):
        release = threading.Event()
        self.addCleanup(release.set)
        def blocked():
            release.wait(2)
            return True
        self.api.is_user_logged_in.side_effect = blocked
        with patch("proton_vpn_kde_backend.adapters.SECRET_STORE_WAIT_SECONDS", 0.02):
            with self.assertRaises(SecretStoreUnavailableError):
                await self.adapter.initialize(self.snapshots.append)
        self.assertEqual(1, self.api.is_user_logged_in.call_count)
        self.waiter.assert_not_awaited()
        self.api.get_vpn_connector.assert_not_awaited()
        release.set()
        await asyncio.sleep(0)
        self.assertFalse(self.adapter._initialized)

    async def test_cancellation_while_waiting_never_retries_credentials(self):
        entered = asyncio.Event()
        async def wait(_timeout):
            entered.set()
            await asyncio.Event().wait()
        self.waiter.side_effect = wait
        self.api.is_user_logged_in.side_effect = KeyringLocked()
        task = asyncio.create_task(self.adapter.initialize(self.snapshots.append))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(1, self.api.is_user_logged_in.call_count)
        self.api.get_vpn_connector.assert_not_awaited()

    async def test_unknown_error_is_not_retried_or_relabelled_as_locked(self):
        self.api.is_user_logged_in.side_effect = ValueError("private")
        with self.assertRaises(ValueError):
            await self.adapter.initialize(self.snapshots.append)
        self.waiter.assert_not_awaited()
        self.assertEqual(1, self.api.is_user_logged_in.call_count)

    async def test_provider_timeout_is_not_an_expired_startup_deadline(self):
        self.api.is_user_logged_in.side_effect = TimeoutError("private provider detail")
        with self.assertRaises(TimeoutError) as caught:
            await self.adapter.initialize(self.snapshots.append)
        self.assertNotIsInstance(caught.exception, SecretStoreUnavailableError)
        self.waiter.assert_not_awaited()
        self.assertEqual(1, self.api.is_user_logged_in.call_count)
        self.api.get_vpn_connector.assert_not_awaited()

    async def test_provider_timeout_after_unlock_is_still_an_unknown_failure(self):
        self.api.is_user_logged_in.side_effect = [KeyringLocked(), TimeoutError()]
        self.waiter.return_value = True
        with self.assertRaises(TimeoutError):
            await self.adapter.initialize(self.snapshots.append)
        self.waiter.assert_awaited_once()
        self.assertEqual(2, self.api.is_user_logged_in.call_count)
        self.api.get_vpn_connector.assert_not_awaited()

    async def test_durable_cleanup_retains_its_existing_recovery_boundary(self):
        self.adapter._packet_capture.has_pending_recovery = Mock(return_value=True)
        self.api.is_user_logged_in.side_effect = KeyringLocked()
        with self.assertRaises(KeyringLocked):
            await self.adapter.initialize(self.snapshots.append)
        self.waiter.assert_not_awaited()
        self.api.get_vpn_connector.assert_not_awaited()

    async def test_absent_session_is_still_a_normal_signed_out_startup(self):
        self.api.is_user_logged_in.return_value = False
        snapshot = await self.adapter.initialize(self.snapshots.append)
        self.assertTrue(snapshot.ready)
        self.assertFalse(snapshot.logged_in)
        self.assertEqual("signed_out", snapshot.auth_state)
        self.waiter.assert_not_awaited()

