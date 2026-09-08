# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Account handoff tests use disposable state and fake provider I/O only."""

import asyncio
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core_fakes import core_module_fakes
import test_proton_core_adapter as adapter_tests
from proton_vpn_kde_backend import account_transition
from proton_vpn_kde_backend.account_transition import AccountTransitionJournal
from proton_vpn_kde_backend.adapters import ProtonCoreAdapter


class AccountJournalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "transition.json"
        self.journal = AccountTransitionJournal(self.path)

    def test_round_trip_contains_no_account_or_secret(self):
        self.assertIsNone(self.journal.load())
        self.journal.store(tunnel_retired=False)
        record = self.journal.load()
        self.assertEqual(account_transition.PROCESS_GENERATION, record.process_generation)
        self.assertFalse(record.tunnel_retired)
        self.assertEqual(0o600, stat.S_IMODE(self.path.stat().st_mode))
        self.assertLess(self.path.stat().st_size, 256)
        self.journal.store(tunnel_retired=True)
        self.assertTrue(self.journal.load().tunnel_retired)
        self.journal.clear()
        self.assertIsNone(self.journal.load())

    def test_invalid_or_nonprivate_record_is_not_ignored(self):
        for payload in (b"broken", b"[]", b"{}", b"x" * 257):
            with self.subTest(payload=payload[:10]):
                self.path.write_bytes(payload)
                self.path.chmod(0o600)
                with self.assertRaisesRegex(RuntimeError, "read safely"):
                    self.journal.load()
        self.journal.store(tunnel_retired=True)
        self.path.chmod(0o644)
        with self.assertRaises(RuntimeError):
            self.journal.load()

    def test_symlink_and_fifo_are_rejected_without_following_or_blocking(self):
        self.path.symlink_to(self.path.parent / "missing")
        with self.assertRaises(RuntimeError):
            self.journal.load()
        self.path.unlink()
        os.mkfifo(self.path, 0o600)
        with self.assertRaises(RuntimeError):
            self.journal.load()

    def test_replace_failure_preserves_previous_record(self):
        self.journal.store(tunnel_retired=False)
        with patch.object(account_transition.os, "replace", side_effect=OSError):
            with self.assertRaisesRegex(RuntimeError, "recorded safely"):
                self.journal.store(tunnel_retired=True)
        self.assertFalse(self.journal.load().tunnel_retired)
        self.assertEqual([self.path], list(self.path.parent.iterdir()))


@patch.dict("sys.modules", core_module_fakes())
class AccountHandoffTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        environment = patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.path = Path(directory.name) / "account.json"
        self.journal = AccountTransitionJournal(self.path)

    def make_api(self, *, logged_in=True):
        return adapter_tests.ProtonCoreAdapterTests().make_api(logged_in=logged_in)

    def adapter(self, api):
        return ProtonCoreAdapter(api, account_transition_path=self.path)

    def inherited_record(self, *, tunnel_retired=True):
        with patch.object(account_transition, "PROCESS_GENERATION", "0" * 32):
            self.journal.store(tunnel_retired=tunnel_retired)
        retirement = patch.object(account_transition, "retired_process_confirmed", return_value=True)
        retirement.start()
        self.addCleanup(retirement.stop)

    async def test_new_generation_cannot_bypass_a_still_running_outgoing_process(self):
        with patch.object(account_transition, "PROCESS_GENERATION", "0" * 32):
            self.journal.store(tunnel_retired=True)
        api, _ = self.make_api()
        expected_error = (
            "outgoing backend is still stopping" if hasattr(os, "pidfd_open")
            else "Python build with Linux pidfd support"
        )
        with self.assertRaisesRegex(RuntimeError, expected_error):
            await self.adapter(api).initialize(Mock())
        api.is_user_logged_in.assert_not_called()
        api.refresher.enable.assert_not_awaited()

    async def test_logout_blocks_new_credentials_and_same_process_reinitialization(self):
        api, connector = self.make_api()
        adapter = self.adapter(api)
        await adapter.initialize(Mock())
        await adapter.logout()
        self.assertTrue(self.journal.load().tunnel_retired)
        with self.assertRaisesRegex(RuntimeError, "restart the backend"):
            await adapter.login("another-account", "unused")
        with self.assertRaisesRegex(RuntimeError, "new backend process"):
            await self.adapter(api).initialize(Mock())
        api.login.assert_not_awaited()
        self.assertEqual("Disconnected", type(connector.current_state).__name__)

    async def test_fresh_process_clears_late_restored_session_before_login(self):
        self.inherited_record()
        api, connector = self.make_api()
        connector.current_state = adapter_tests.state_named("Connected")
        sequence = []

        async def logout():
            sequence.append("logout")
            self.assertEqual("Disconnected", type(connector.current_state).__name__)
            api.is_user_logged_in.return_value = False

        async def login(*_args):
            sequence.append("login")
            self.assertIsNone(self.journal.load())
            return SimpleNamespace(authenticated=True, twofa_required=False)

        api.logout.side_effect = logout
        api.login.side_effect = login
        adapter = self.adapter(api)
        snapshot = await adapter.initialize(Mock())
        self.assertFalse(snapshot.logged_in)
        self.assertEqual("signed_out", snapshot.auth_state)
        api.refresher.enable.assert_not_awaited()
        await adapter.login("replacement-account", "unused")
        self.assertEqual(["logout", "login"], sequence)
        api.refresher.enable.assert_awaited_once()

    async def test_partial_record_can_recover_using_restorable_old_session(self):
        self.inherited_record(tunnel_retired=False)
        api, _ = self.make_api()

        async def logout():
            api.is_user_logged_in.return_value = False

        api.logout.side_effect = logout
        await self.adapter(api).initialize(Mock())
        self.assertIsNone(self.journal.load())
        api.refresher.enable.assert_not_awaited()

    async def test_unconfirmed_tunnel_without_session_blocks_startup(self):
        self.inherited_record(tunnel_retired=False)
        api, _ = self.make_api(logged_in=False)
        with self.assertRaisesRegex(RuntimeError, "tunnel cleanup is unconfirmed"):
            await self.adapter(api).initialize(Mock())
        self.assertIsNotNone(self.journal.load())
        api.refresher.enable.assert_not_awaited()
        api.logout.assert_not_awaited()

    async def test_uncleared_persisted_session_blocks_readiness_and_refresh(self):
        self.inherited_record()
        api, _ = self.make_api()
        # A successful coroutine return is insufficient when Core still sees
        # the old saved account. The handoff must not be acknowledged.
        with self.assertRaisesRegex(RuntimeError, "outgoing Proton account"):
            await self.adapter(api).initialize(Mock())
        self.assertIsNotNone(self.journal.load())
        api.refresher.enable.assert_not_awaited()

    async def test_startup_account_cleanup_has_a_terminal_deadline(self):
        self.inherited_record()
        api, _ = self.make_api()
        release = asyncio.Event()
        children = []
        adapter = ProtonCoreAdapter(
            api, account_transition_path=self.path,
            connection_retirement_seconds=0.01,
            terminal_exit=Mock(side_effect=RuntimeError("simulated process exit")),
        )

        async def stuck_cleanup():
            children.append(asyncio.current_task())
            await release.wait()

        adapter._finish_account_restart = stuck_cleanup
        self.assertTrue(adapter.has_pending_startup_recovery())
        try:
            with self.assertLogs("proton_vpn_kde_backend.adapters", level="CRITICAL"):
                with self.assertRaisesRegex(RuntimeError, "simulated process exit"):
                    await adapter.initialize(Mock())
            self.assertIsNotNone(self.journal.load())
            api.refresher.enable.assert_not_awaited()
            adapter._terminal_exit.assert_called_once_with(1)
        finally:
            release.set()
            await asyncio.gather(*children)

    async def test_expiry_preserves_established_tunnel_until_sign_in_preparation(self):
        api, connector = self.make_api()
        connector.current_state = adapter_tests.state_named("Connected")
        adapter = self.adapter(api)
        await adapter.initialize(Mock())
        await adapter._expire_session(adapter._authentication_epoch)
        connector.disconnect.assert_not_awaited()
        with self.assertRaisesRegex(RuntimeError, "restart the backend"):
            await adapter.login("replacement", "unused")
        self.assertIsNone(self.journal.load())
        await adapter.logout()
        connector.disconnect.assert_awaited_once()
        self.assertTrue(self.journal.load().tunnel_retired)

    async def test_caller_cancel_cannot_admit_replacement_during_cleanup(self):
        api, connector = self.make_api()
        entered, release = asyncio.Event(), asyncio.Event()

        async def disconnect():
            entered.set()
            await release.wait()
            connector.current_state = adapter_tests.state_named("Disconnected")

        connector.disconnect.side_effect = disconnect
        adapter = self.adapter(api)
        await adapter.initialize(Mock())
        logout = asyncio.create_task(adapter.logout())
        await entered.wait()
        logout.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await logout
        with self.assertRaisesRegex(RuntimeError, "restart the backend"):
            await adapter.login("replacement", "unused")
        self.assertIsNotNone(self.journal.load())
        api.login.assert_not_awaited()


class ProcessRetirementTests(unittest.TestCase):
    def test_unavailable_pidfd_api_fails_closed(self):
        record = account_transition.AccountTransition("0" * 32, True, os.getpid(), 1)
        with patch.object(os, "pidfd_open", None, create=True):
            with self.assertRaisesRegex(RuntimeError, "Python build with Linux pidfd support"):
                account_transition.retired_process_confirmed(record)

    @unittest.skipUnless(hasattr(os, "pidfd_open"), "Python build omits Linux pidfd API")
    def test_pidfd_distinguishes_running_and_exited_process(self):
        with subprocess.Popen(
            [sys.executable, "-c", "import sys; print('ready', flush=True); sys.stdin.read(1)"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        ) as child:
            try:
                self.assertEqual("ready", child.stdout.readline().strip())
                record = account_transition.AccountTransition(
                    "0" * 32, True, child.pid,
                    account_transition.process_start_ticks(child.pid),
                )
                self.assertFalse(account_transition.retired_process_confirmed(record))
                child.communicate("x", timeout=2)
                self.assertTrue(account_transition.retired_process_confirmed(record))
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=2)
