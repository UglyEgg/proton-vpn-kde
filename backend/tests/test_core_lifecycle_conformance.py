# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Opt-in actual-Core event-order tests; never construct the live API or NM.

Set PLASMA_VPN_TEST_CORE_SITE_PACKAGES to a hash-checked Core site-packages tree.
Unlike unit fakes, these use the unmodified connector event dispatcher and
state tasks, plus the public refresher error forwarder and actual scheduler.
All external I/O and publication are substituted explicitly.
"""

import asyncio
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from proton_vpn_kde_backend.adapters import ProtonCoreAdapter
from proton_vpn_kde_backend.core_servers import FastestSelection
from proton_vpn_kde_backend.reconnector import AsyncReconnector
import test_proton_core_adapter as adapter_tests


class RetirementRejected(RuntimeError):
    """Replace process exit in this isolated conformance harness."""


@unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_CORE_SITE_PACKAGES"),
                     "explicit hash-checked Core conformance fixture required")
class CoreLifecycleConformanceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Core constructs paths during import, before per-test setUp runs.
        cls.environment_root = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        directories = {}
        for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
            directory = cls.environment_root / name.lower()
            directory.mkdir(mode=0o700)
            directories[name] = str(directory)
        cls.enterClassContext(patch.dict(os.environ, directories))
        # PyXDG caches these two paths at import; discovery may import it first.
        from xdg import BaseDirectory
        cls.enterClassContext(patch.object(BaseDirectory, "xdg_config_home", directories["XDG_CONFIG_HOME"]))
        cls.enterClassContext(patch.object(BaseDirectory, "xdg_cache_home", directories["XDG_CACHE_HOME"]))
        source = Path(os.environ["PLASMA_VPN_TEST_CORE_SITE_PACKAGES"]).resolve()
        # These provider modules are unchanged by our packaging overlays.
        expected = {
            "proton/vpn/core/vpnconnector.py": {
                "56166d64f78fea439d430266753ae5591341b8501ea38e0f6c3f61f732162ebf",  # 5.6.20
                "70ad34fbb32f1da9a87d794886c06b27cd87d0eb5c4a4edfb606540b25922f88",  # 5.8.3 / 5.8.11
            },
            "proton/vpn/connection/states.py": {
                "1c54923e121d36c8c57c606addc64afb4d1d0c768a99084966de0664813968fe",  # 5.6.20
                "2cd1900bd5c743a865ac49cf563ea45e5c90af018683176fb87a585deb86a83d",  # 5.8.3 / 5.8.11
            },
            "proton/vpn/core/refresher/scheduler.py": {
                "a4830c8b24645e59d8ec4b47180b2afd0e72bc2c7d685da9ecb15647eb886449",
            },
            "proton/vpn/core/refresher/vpn_data_refresher.py": {
                "80117ee317910e528a129a0c0d10bcda873f48234e372555bfbab54d3e478804",  # 5.6.20
                "91252db9086e4231923b6d35d2456790ce4940b05fb948ca9a291d4ce1310b2b",  # 5.8.3
                "8521adbd48c4d20743294ef1deb9b1ed9ab836a424310cf991296e505a81e993",  # 5.8.11
            },
        }
        for relative, digests in expected.items():
            if hashlib.sha256((source / relative).read_bytes()).hexdigest() not in digests:
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

    def test_import_time_paths_are_disposable(self):
        settings = importlib.import_module("proton.vpn.core.settings.settings")
        from proton.utils.environment import VPNExecutionEnvironment
        environment = VPNExecutionEnvironment()
        for path in (settings.SETTINGS, environment._path_config,
                     environment._path_cache, environment._path_runtime):
            self.assertTrue(Path(path).is_relative_to(self.environment_root), path)
        self.assertEqual(self.environment_root.stat().st_mode & 0o077, 0)

    def test_fastest_scope_views_retain_real_core_group_semantics_and_work_bounds(self):
        from proton.vpn.session.servers import LogicalServer, ServerList

        def logical(identifier, *, country="CH", location="Zurich", tier=2,
                    features=12, score=9):
            return LogicalServer({
                "ID": identifier, "Name": identifier, "EntryCountry": country,
                "ExitCountry": country, "City": location, "Tier": tier,
                "Status": 1, "Features": features, "Score": score, "Load": 0,
                "Servers": [{"ID": identifier, "Status": 1}],
            })

        catalog = ServerList(user_tier=2, logicals=[
            logical("current"), logical("nearby", score=5),
            logical("geneva", location="Geneva", score=1),
            logical("free", tier=0, score=0),
            logical("secure", features=13, score=2),
            logical("foreign", country="US", score=3),
        ])
        location = FastestSelection(country_code="CH", group_kind="location",
                                    group_name="Zurich", features=("p2p", "streaming"))
        secure = FastestSelection(country_code="CH", group_kind="secure-core",
                                  group_name="Via Secure Core", features=("secure-core", "p2p"))
        preferred_cases = (
            (FastestSelection(), "current"),
            (FastestSelection(country_code="CH"), "current"),
            (FastestSelection(country_code="CH", features=()), "current"),
            (location, "current"), (secure, "secure"),
        )
        projected, filtered = [], []
        group_by_country = ServerList.group_by_country
        get_available = ServerList.get_available_servers

        def grouping(view, **kwargs):
            projected.append(len(view.logicals))
            return group_by_country(view, **kwargs)

        def available(servers, tier):
            selected = list(servers)
            filtered.append(len(selected))
            return get_available(selected, tier)

        order = [s.id for s in catalog.logicals]
        with patch.object(ServerList, "group_by_country", grouping), \
             patch.object(ServerList, "get_available_servers", staticmethod(available)):
            for selection, identifier in preferred_cases:
                with self.subTest(selection=selection):
                    self.assertIs(catalog.get_by_id(identifier), selection.pick(catalog, identifier, set()))
        self.assertEqual([1, 1], projected)
        self.assertEqual([1] * len(preferred_cases), filtered)
        self.assertEqual("nearby", location.pick(catalog, "", {"current"}).id)
        self.assertEqual("secure", secure.pick(catalog, "", set()).id)
        # A paid location excludes free and Secure Core records; country
        # selection does not. Both remain Core-owned grouping behavior.
        self.assertEqual("free", FastestSelection(country_code="CH", features=()).pick(
            catalog, "", set()).id)
        self.assertEqual(order, [s.id for s in catalog.logicals])
        free_catalog = ServerList(user_tier=0, logicals=catalog.logicals)
        self.assertEqual("free", location.pick(free_catalog, "", set()).id)

    def test_cold_import_without_desktop_environment(self):
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            str(Path(path).resolve()) for path in environment.get("PYTHONPATH", "").split(os.pathsep) if path
        )
        for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
            environment.pop(name, None)
        program = (
            "from xdg import BaseDirectory\n"  # Cache paths before fixture setup.
            "import unittest\n"
            "suite = unittest.defaultTestLoader.loadTestsFromName("
            "'test_core_lifecycle_conformance.CoreLifecycleConformanceTests."
            "test_import_time_paths_are_disposable')\n"
            "result = unittest.TextTestRunner().run(suite)\n"
            "raise SystemExit(not result.wasSuccessful())\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", program], cwd=Path(__file__).parent,
            env=environment, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        runtime = patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory.name})
        runtime.start()
        self.addCleanup(runtime.stop)
        self.kill_switch = SimpleNamespace(enable=AsyncMock(), disable=AsyncMock(),
                                          enable_ipv6_leak_protection=AsyncMock(),
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
        return SimpleNamespace(remove_persistence=AsyncMock(), register=Mock(), unregister=Mock(),
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

    async def crash_recovery(
        self, mode, *, failures=0, checkpoint=lambda _stage: None, fastest=False,
    ):
        """Real public Core Up, dispatcher and state tasks; only external I/O is fake."""
        trace, queued, attempts, errors = [], [], [], []
        connected = asyncio.Event()
        old = self.connection()
        old.add_persistence = AsyncMock()
        old.server_id, old.protocol, old.backend = "server-id", "protun-smart", "linuxnetworkmanager"
        self.connector._current_state = self.states.Connected(
            self.states.StateContext(connection=old)
        )
        self.connector._publisher = self.connector_module.Publisher()
        self.connector._publisher.register(self.adapter.status_update)
        self.connector._split_tunneling = None
        self.connector._session_holder = SimpleNamespace(
            session=SimpleNamespace(logged_in=True), user_tier=2, vpn_credentials=object()
        )
        self.connector.get_settings = AsyncMock(return_value=SimpleNamespace(
            killswitch=mode, protocol="protun-smart",
            features=SimpleNamespace(split_tunneling=SimpleNamespace(enabled=False)),
        ))
        self.adapter._logged_in = True

        def emit(event):
            queued.append(asyncio.create_task(self.connector._on_connection_event(event)))

        def protocol(vpn_server, *_args):
            connection = self.connection()
            connection.add_persistence = AsyncMock()
            connection.server_id, connection.protocol, connection.backend = (
                getattr(vpn_server, "id", old.server_id), old.protocol, old.backend
            )

            async def start():
                attempts.append(connection)
                checkpoint("starting")
                trace.append("start")
                event = self.events.Timeout if len(attempts) <= failures else self.events.Connected
                if event is self.events.Connected:
                    checkpoint("restoring")
                emit(event(self.events.EventContext(connection=connection)))

            async def stop():
                checkpoint("stopping")
                trace.append("stop")
                emit(self.events.Disconnected(self.events.EventContext(connection=connection)))

            connection.start.side_effect, connection.stop.side_effect = start, stop
            return connection

        async def stop_old():
            checkpoint("stopping")
            trace.append("stop")
            emit(self.events.Disconnected(self.events.EventContext(connection=old)))

        async def enable(*_args, **kwargs):
            checkpoint("connected" if isinstance(self.connector.current_state, self.states.Connected) else "protecting")
            trace.append(("protect", kwargs.get("permanent", False)))

        async def disable():
            # The OFF setting releases the temporary protection only *after*
            # Core has received Connected for the replacement connection.
            self.assertIsInstance(self.connector.current_state, self.states.Connected)
            checkpoint("connected")
            trace.append("release-temporary-protection")

        old.stop.side_effect = stop_old
        self.kill_switch.enable.side_effect = enable
        self.kill_switch.disable.side_effect = disable
        self.connector._registry = SimpleNamespace(get=Mock(return_value=protocol))
        self.connector.get_vpn_server = Mock(return_value=old.server)
        refresher = SimpleNamespace(
            server_list=SimpleNamespace(get_by_id=Mock(return_value=object())), client_config=object()
        )
        if fastest:
            from proton.vpn.session.servers import ServerFeatureEnum as Feature, ServerList
            # Real Core availability, feature intersection and score selection;
            # only the server records and privileged I/O are synthetic.
            refresher.server_list = ServerList(user_tier=2, logicals=[
                SimpleNamespace(id=identifier, name=identifier, score=index,
                                enabled=True, tier=1, features=[Feature.P2P, Feature.STREAMING])
                for index, identifier in enumerate(("server-id", "alternative-1", "alternative-2"))
            ])
            self.connector.get_vpn_server = Mock(side_effect=lambda logical, _config: logical)
        delays = []

        def retry_delay(counter):
            delays.append(counter)
            return 0

        async def attempt(*args):
            try:
                return await self.adapter._attempt_reconnection(*args)
            except Exception as error:
                errors.append(error)
                connected.set()
                return False

        reconnector = AsyncReconnector(
            self.connector, refresher, connection_attempt=attempt,
            authentication_epoch_source=lambda: self.adapter._authentication_epoch,
            authentication_epoch_validator=lambda epoch: epoch == self.adapter._authentication_epoch,
            authentication_error_callback=AsyncMock(), delay_factory=retry_delay,
            session_probe=SimpleNamespace(is_unlocked=AsyncMock(return_value=True), close=AsyncMock()),
            fastest_selection_source=lambda: (
                FastestSelection(features=("p2p", "streaming")) if fastest else None
            ),
        )

        def observe(state):
            if isinstance(state, self.states.Connected) and state.context.connection is not old:
                connected.set()

        self.connector._publisher.register(observe)
        with patch.object(self.states.StateContext, "kill_switch_setting", mode):
            reconnector.enable()
            try:
                await self.connector._on_connection_event(
                    self.events.UnexpectedError(self.events.EventContext(connection=old))
                )
                await asyncio.wait_for(connected.wait(), timeout=2)
                if errors:
                    raise errors[0]
                await asyncio.gather(*queued)
            finally:
                await reconnector.disable()
                await asyncio.gather(*queued)
        self.assertEqual(failures + 1, len(attempts))
        if fastest:
            self.assertEqual(
                ["server-id", "server-id", "alternative-1", "alternative-1", "alternative-2"],
                [connection.server_id for connection in attempts],
            )
        self.assertEqual(list(range(failures + 1)), delays)
        self.assertEqual("stop", trace[0])
        for index, step in enumerate(trace):
            if step == "start":
                self.assertEqual(("protect", mode == self.states.KillSwitchSetting.PERMANENT), trace[index - 1])
        self.assertEqual(int(mode == self.states.KillSwitchSetting.OFF), trace.count("release-temporary-protection"))
        self.kill_switch.disable_ipv6_leak_protection.assert_not_awaited()
        self.adapter._terminal_exit.assert_not_called()
        self.assertIsNone(reconnector._retry_task)

    async def test_crash_recovery_preserves_all_kill_switch_modes(self):
        for mode in self.states.KillSwitchSetting:
            with self.subTest(mode=mode):
                await self.crash_recovery(mode)

    async def test_crash_recovery_retries_unreachable_server_without_unprotecting(self):
        for mode in self.states.KillSwitchSetting:
            with self.subTest(mode=mode):
                await self.crash_recovery(mode, failures=2)

    async def test_fastest_failover_preserves_real_core_protected_handoffs(self):
        for mode in self.states.KillSwitchSetting:
            with self.subTest(mode=mode):
                await self.crash_recovery(mode, failures=4, fastest=True)

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_NAMESPACE_PARENT"),
                         "explicit isolated network namespace required")
    async def test_isolated_crash_routing_replay(self):
        await self.isolated_crash_routing_replay()

    async def test_namespace_guard_rejects_parent_before_network_mutations(self):
        for parent_net in (os.readlink("/proc/self/ns/net"), "different-network-namespace"):
            with self.subTest(parent_net=parent_net), patch.dict(os.environ, {
                "PLASMA_VPN_TEST_NAMESPACE_PARENT": parent_net,
                "PLASMA_VPN_TEST_USER_NAMESPACE_PARENT": os.readlink("/proc/self/ns/user"),
            }), patch("subprocess.run") as command:
                with self.assertRaises(AssertionError):
                    await self.isolated_crash_routing_replay()
                command.assert_not_called()

    async def isolated_crash_routing_replay(self):
        # Refuse every network mutation unless a launcher created a fresh,
        # empty namespace. There is no host-side fallback, NM, or external link.
        self.assertNotEqual(os.readlink("/proc/self/ns/net"), os.environ["PLASMA_VPN_TEST_NAMESPACE_PARENT"])
        self.assertNotEqual(os.readlink("/proc/self/ns/user"), os.environ["PLASMA_VPN_TEST_USER_NAMESPACE_PARENT"])

        def ip(*args, check=True):
            return subprocess.run(["/usr/bin/ip", *args], check=check, capture_output=True,
                                  text=True, timeout=2)

        self.assertEqual(["lo"], [link["ifname"] for link in json.loads(ip("-j", "link", "show").stdout)])
        ip("link", "add", "underlay0", "type", "dummy")
        ip("link", "set", "underlay0", "up")
        for family, address in (
            ("-4", "192.0.2.2/24"),
            ("-6", "2001:db8:1::2/64"),
        ):
            ip(family, "address", "add", address, "dev", "underlay0", "nodad")
            ip(family, "route", "add", "default", "dev", "underlay0")
            ip(family, "route", "add", "unreachable", "default", "table", "245447468", "metric", "100")
            ip(family, "rule", "add", "priority", "32764", "table", "main", "suppress_prefixlength", "0")
            ip(family, "rule", "add", "priority", "32765", "not", "fwmark", "245447468", "table", "245447468")

        rules = {family: ip(family, "rule", "show").stdout for family in ("-4", "-6")}

        def tunnel():
            ip("link", "add", "proton0", "type", "dummy")
            ip("link", "set", "proton0", "up")
            for family in ("-4", "-6"):
                ip(family, "route", "add", "default", "dev", "proton0", "table", "245447468", "metric", "50")

        def checkpoint(stage):
            if stage == "restoring":
                tunnel()
            for family, destination in (("-4", "198.51.100.1"), ("-6", "2001:db8:2::1")):
                self.assertEqual(rules[family], ip(family, "rule", "show").stdout)
                self.assertIn("unreachable default", ip(family, "route", "show", "table", "245447468").stdout)
                lookup = ip(family, "route", "get", destination, check=False)
                if stage in {"restoring", "connected"}:
                    self.assertEqual(0, lookup.returncode, lookup.stderr)
                    self.assertIn("dev proton0", lookup.stdout)
                else:
                    self.assertNotEqual(0, lookup.returncode)  # no underlay fallback

        for mode in self.states.KillSwitchSetting:
            with self.subTest(mode=mode):
                tunnel()
                # Replay the kernel consequence of SIGKILL: the tunnel link and
                # its route vanish, while native policy rules/fallbacks survive.
                ip("link", "delete", "proton0")
                try:
                    checkpoint("crashed")
                    await self.crash_recovery(mode, failures=2, checkpoint=checkpoint)
                    checkpoint("connected")
                finally:
                    ip("link", "delete", "proton0", check=False)

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
