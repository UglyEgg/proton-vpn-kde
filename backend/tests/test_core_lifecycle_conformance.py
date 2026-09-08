# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Opt-in actual-Core event-order tests; never construct the live API or NM.

Set PLASMA_VPN_TEST_CORE_SITE_PACKAGES to a Core 5.6.10 site-packages tree.
Unlike unit fakes, these use the unmodified connector event dispatcher and
state tasks, plus the public refresher error forwarder and actual scheduler.
All external I/O and publication are substituted explicitly.
"""

import asyncio
import hashlib
import importlib
import inspect
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from proton_vpn_kde_backend.adapters import ProtonCoreAdapter
import test_proton_core_adapter as adapter_tests


class RetirementRejected(RuntimeError):
    """Replace process exit in this isolated conformance harness."""


@unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_CORE_SITE_PACKAGES"),
                     "explicit Core 5.6.10 conformance fixture required")
class CoreLifecycleConformanceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ["PLASMA_VPN_TEST_CORE_SITE_PACKAGES"]).resolve()
        # These provider modules are unchanged by our packaging overlays.
        expected = {
            "proton/vpn/core/vpnconnector.py":
                "3ff83e99d3ae138a91fc4a393c82eb811212020736bbb499228b7ef22f52ccda",
            "proton/vpn/connection/states.py":
                "1c54923e121d36c8c57c606addc64afb4d1d0c768a99084966de0664813968fe",
            "proton/vpn/core/refresher/scheduler.py":
                "a4830c8b24645e59d8ec4b47180b2afd0e72bc2c7d685da9ecb15647eb886449",
            "proton/vpn/core/refresher/vpn_data_refresher.py":
                "cbeb460254d8535d7a51f61e647865d3684f5e5506ff10ea0087fe6a8bdd67a7",
        }
        for relative, digest in expected.items():
            if hashlib.sha256((source / relative).read_bytes()).hexdigest() != digest:
                raise AssertionError("Core lifecycle fixture changed; review its contract")
        sys.path.insert(0, str(source))
        cls.addClassCleanup(sys.path.remove, str(source))
        cls.connector_module = importlib.import_module("proton.vpn.core.vpnconnector")
        cls.states = importlib.import_module("proton.vpn.connection.states")
        cls.events = importlib.import_module("proton.vpn.connection.events")
        cls.scheduler = importlib.import_module("proton.vpn.core.refresher.scheduler")
        cls.refresher = importlib.import_module("proton.vpn.core.refresher.vpn_data_refresher")
        for module, relative in ((cls.connector_module, "proton/vpn/core/vpnconnector.py"),
                                 (cls.states, "proton/vpn/connection/states.py"),
                                 (cls.scheduler, "proton/vpn/core/refresher/scheduler.py"),
                                 (cls.refresher, "proton/vpn/core/refresher/vpn_data_refresher.py")):
            if Path(inspect.getfile(module)).resolve() != source / relative:
                raise AssertionError("The imported Core differs from the selected fixture")

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        runtime = patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory.name})
        runtime.start()
        self.addCleanup(runtime.stop)
        self.kill_switch = SimpleNamespace(enable=AsyncMock(), disable=AsyncMock(),
                                          disable_ipv6_leak_protection=AsyncMock())
        for name, value in (("kill_switch", self.kill_switch),
                            ("kill_switch_setting", self.states.KillSwitchSetting.OFF),
                            ("split_tunneling", None)):
            replacement = patch.object(self.states.StateContext, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.adapter = ProtonCoreAdapter(
            api=object(), terminal_exit=Mock(side_effect=RetirementRejected),
            connection_retirement_seconds=2,
        )
        # Bypass construction and initialize_state: those are live integration
        # paths. Only the real public Down + locked event/state tasks execute.
        self.connector = object.__new__(self.connector_module.VPNConnector)
        self.connector._lock = asyncio.Lock()
        self.connector._publisher = SimpleNamespace(notify=self.adapter.status_update)
        self.connector._usage_reporting = Mock()
        self.connector._set_ks_impl = Mock()
        self.connector.get_settings = AsyncMock(return_value=SimpleNamespace(protocol="wireguard"))
        self.adapter._connector = self.connector

    def connection(self):
        return SimpleNamespace(remove_persistence=AsyncMock(), unregister=Mock(),
                               start=AsyncMock(), stop=AsyncMock(), server=object())

    async def paused_teardown(self, *, replacement):
        old = self.connection()
        entered, release = asyncio.Event(), asyncio.Event()

        async def remove_persistence():
            entered.set()
            await release.wait()

        old.remove_persistence.side_effect = remove_persistence
        self.connector._current_state = self.states.Disconnecting(
            self.states.StateContext(connection=old, reconnection=replacement)
        )
        teardown = asyncio.create_task(self.connector._on_connection_event(
            self.events.Disconnected(self.events.EventContext(connection=old))
        ))
        await asyncio.wait_for(entered.wait(), timeout=1)
        self.assertIsInstance(self.connector.current_state, self.states.Disconnected)
        return release, teardown

    async def test_disconnected_property_does_not_complete_pending_event(self):
        release, teardown = await self.paused_teardown(replacement=None)
        retirement = asyncio.create_task(self.adapter._disconnect_until_stable(
            transitional_only=True
        ))
        try:
            for _ in range(5):
                await asyncio.sleep(0)
            self.assertFalse(retirement.done())
        finally:
            release.set()
            await asyncio.wait_for(teardown, timeout=1)
            await asyncio.wait_for(retirement, timeout=1)
        self.adapter._terminal_exit.assert_not_called()
        self.kill_switch.disable.assert_awaited_once()

    async def test_queued_identity_change_is_unconfirmed_not_false_success(self):
        replacement = self.connection()
        release, teardown = await self.paused_teardown(replacement=replacement)
        retirement = asyncio.create_task(self.adapter._disconnect_until_stable(
            transitional_only=True
        ))
        try:
            for _ in range(5):
                await asyncio.sleep(0)
            self.assertFalse(retirement.done())
        finally:
            release.set()
            await asyncio.wait_for(teardown, timeout=1)
            with self.assertLogs("proton_vpn_kde_backend.adapters", level="CRITICAL"):
                with self.assertRaises(RetirementRejected):
                    await asyncio.wait_for(retirement, timeout=1)
        replacement.start.assert_awaited_once()
        self.adapter._terminal_exit.assert_called_once_with(1)

    async def test_established_tunnel_is_preserved_for_transitional_retirement(self):
        connection = self.connection()
        self.connector._current_state = self.states.Connected(
            self.states.StateContext(connection=connection)
        )
        await self.adapter._disconnect_until_stable(transitional_only=True)
        connection.stop.assert_not_awaited()
        self.adapter._terminal_exit.assert_not_called()

    async def scheduler_error_case(self, error, expected_auth_state):
        api, connector = adapter_tests.ProtonCoreAdapterTests().make_api()
        connector.current_state = adapter_tests.state_named("Connected")
        scheduler = self.scheduler.Scheduler()
        # Bypass the Core refresher constructor and all refresh I/O, but use
        # its real public forwarding method and scheduler exception dispatch.
        refresher = object.__new__(self.refresher.VPNDataRefresher)
        refresher._scheduler = scheduler
        api.refresher.set_error_callback = refresher.set_error_callback

        async def failed_refresh():
            raise error

        async def enable():
            scheduler.run_soon(failed_refresh)
            scheduler.start()

        api.refresher.enable.side_effect = enable
        api.refresher.disable.side_effect = scheduler.stop
        adapter = ProtonCoreAdapter(api)
        snapshots, unhandled = [], []
        published = asyncio.Event()

        def snapshot_changed(snapshot):
            snapshots.append(snapshot)
            if snapshot.auth_state == expected_auth_state:
                published.set()

        loop = asyncio.get_running_loop()
        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda _loop, context: unhandled.append(context))
        try:
            await adapter.initialize(snapshot_changed)
            await asyncio.wait_for(published.wait(), 1)
            self.assertEqual("connected", snapshots[-1].state)
            connector.disconnect.assert_not_awaited()
            self.assertEqual([], scheduler.task_list)
            await adapter.close()
            await asyncio.sleep(0)
            self.assertEqual([], unhandled)
            self.assertFalse(scheduler.is_started)
        finally:
            # Only an isolated scheduler is stopped; no real API or NM exists.
            await scheduler.stop()
            loop.set_exception_handler(original_handler)

    async def test_real_scheduler_authentication_failure_enters_expiry(self):
        error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})()
        await self.scheduler_error_case(error, "expired")

    async def test_real_scheduler_update_failure_reports_degraded_services(self):
        await self.scheduler_error_case(RuntimeError("unused details"), "signed_in_degraded")
