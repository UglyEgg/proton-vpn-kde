# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Opt-in actual-Core event-order tests; never construct the live API or NM.

Set PLASMA_VPN_TEST_CORE_SITE_PACKAGES to a hash-checked Core site-packages tree.
Unlike unit fakes, these use the unmodified connector event dispatcher and
state tasks, plus the public refresher error forwarder and actual scheduler.
All external I/O and publication are substituted explicitly.
"""

import asyncio
import base64
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
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from proton_vpn_kde_backend.adapters import ProtonCoreAdapter
from proton_vpn_kde_backend.core_servers import FastestSelection
from proton_vpn_kde_backend.controller import BackendController
from proton_vpn_kde_backend.errors import ConnectorStartupError
from proton_vpn_kde_backend.reconnector import AsyncReconnector
from proton_vpn_kde_backend.secret_service_readiness import require_secret_service_backend
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
        sso_path = os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES")
        if sso_path:
            sso_source = Path(sso_path).resolve()
            # Base Core 0.7.4; SSO includes the installed single-read overlay.
            sso_hashes = {
                "proton/sso/sso.py": "be8fdb9bf62c2a1e207ae03d627a05b375f743b08d8aac2f30bd73a6f688e760",
                "proton/loader/loader.py": "8ba14ff555647338138ddc4b69ff818cfe129a3a058ef33a7761047b94c0a21c",
                "proton/keyring/_base.py": "3f7f75042723558b5853c9c94d2c413b80e96958a807ac67850d315b62ec05ab",
                "proton/keyring/textfile.py": "06dfa739c2a309273523cb5c04896b02b164688290b54568603a91509f398d78",
                "proton/session/api.py": "64554fc97c29c04758d8102e52d5168303ec0523799f73db6238e8e35644a109",
            }
            for relative, digest in sso_hashes.items():
                if hashlib.sha256((sso_source / relative).read_bytes()).hexdigest() != digest:
                    raise AssertionError("SSO/Loader fixture changed; review its contract")
            sys.path.insert(0, str(sso_source))
            cls.addClassCleanup(sys.path.remove, str(sso_source))
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
            "proton/vpn/core/refresher/certificate_refresher.py": {
                "2727199f8bda6b5c566064d10347bcd23f62d765c010cb75560a2df9e610e593",  # 5.8.11
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
        cls.certificates = importlib.import_module("proton.vpn.core.refresher.certificate_refresher")
        if sso_path:
            for relative in sso_hashes:
                module = importlib.import_module(relative[:-3].replace("/", "."))
                if Path(inspect.getfile(module)).resolve() != sso_source / relative:
                    raise AssertionError("Imported SSO/Loader differs from the selected fixture")
            for relative, digest in {
                "proton/vpn/core/api.py": "aa2c46e627999ad88b5276a020f5085f5286a7cd9080c81a7d27836960d18e4b",
                "proton/vpn/core/session_holder.py": "906f740c4511826d7b361c344f098fb6588d3ef0f3f49d2fe25019f26bf07741",
                "proton/vpn/session/session.py": "a1d5fd0ba4b1dbb07f3628e6510b2ca865b4c77c89b51a0131d62860d360a2b2",
            }.items():
                if hashlib.sha256((source / relative).read_bytes()).hexdigest() != digest:
                    raise AssertionError("Core SSO facade fixture changed; review its contract")
                module = importlib.import_module(relative[:-3].replace("/", "."))
                if Path(inspect.getfile(module)).resolve() != source / relative:
                    raise AssertionError("Imported Core SSO facade differs from the fixture")
        for module, relative in ((cls.connector_module, "proton/vpn/core/vpnconnector.py"),
                                 (cls.states, "proton/vpn/connection/states.py"),
                                 (cls.scheduler, "proton/vpn/core/refresher/scheduler.py"),
                                 (cls.certificates, "proton/vpn/core/refresher/certificate_refresher.py"),
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

    async def stale_certificate_failure(self, mode):
        api, connector = adapter_tests.ProtonCoreAdapterTests().make_api()
        connector.current_state = adapter_tests.state_named("Connected")
        scheduler = self.scheduler.Scheduler(check_interval_in_ms=1)
        old_started, new_started = asyncio.Event(), asyncio.Event()
        old_failure, finish_new = asyncio.Event(), asyncio.Event()
        reported, degraded, updated = asyncio.Event(), asyncio.Event(), asyncio.Event()
        fetches, cancelled = [], []

        async def fetch():
            fetches.append(len(fetches) + 1)
            if len(fetches) == 1:
                old_started.set()
                if mode == "cancellation":
                    try:
                        await asyncio.Event().wait()
                    except asyncio.CancelledError:
                        await old_failure.wait()
                        raise RuntimeError("synthetic old-worker persistence failure") from None
                await old_failure.wait()
                raise RuntimeError("synthetic old-worker failure")
            new_started.set()
            try:
                await finish_new.wait()
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
            return SimpleNamespace(remaining_time_to_next_refresh=3600)

        certificate = self.certificates.CertificateRefresher(SimpleNamespace(
            session=SimpleNamespace(fetch_certificate=fetch),
        ))
        certificate.certificate_updated_callback = AsyncMock(side_effect=updated.set)
        refresher = object.__new__(self.refresher.VPNDataRefresher)
        refresher._scheduler = scheduler
        refresher._certificate_refresher = certificate
        refresher._certificate_refresher_task_id = None
        api.refresher.force_refresh_certificate = Mock(wraps=refresher.force_refresh_certificate)
        api.refresher.disable.side_effect = scheduler.stop
        adapter = ProtonCoreAdapter(api)
        snapshots, unhandled = [], []

        def changed(snapshot):
            snapshots.append(snapshot)
            if snapshot.auth_state == "signed_in_degraded":
                degraded.set()

        def expired():
            connector.current_state = adapter_tests.state_named("Error")
            connector.current_state.context = SimpleNamespace(event=self.events.ExpiredCertificate(None))
            adapter._reconnector.status_update(connector.current_state)

        loop = asyncio.get_running_loop()
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda _loop, context: unhandled.append(context))
        try:
            await adapter.initialize(changed)
            callback = api.refresher.set_error_callback.call_args.args[0]
            api.refresher.set_error_callback.side_effect = refresher.set_error_callback
            def report(error):
                callback(error)
                reported.set()
            refresher.set_error_callback(report)
            if mode == "episode-reset":
                expired()
            else:
                refresher._certificate_refresher_task_id = scheduler.run_soon(certificate.refresh)
            scheduler.start()
            await asyncio.wait_for(old_started.wait(), 1)
            if mode == "cancellation":
                expired()  # Cancel old worker; it fails only after its successor starts.
                await asyncio.wait_for(new_started.wait(), 1)
                old_failure.set()
            else:
                async with adapter._serialized_authentication_transition():
                    old_failure.set()
                    await asyncio.wait_for(reported.wait(), 1)
                    if mode == "episode-reset":
                        connector.current_state = adapter_tests.state_named("Disconnected")
                        adapter._reconnector.status_update(connector.current_state)
                    expired()  # An old failure is queued behind the authentication owner.
            await asyncio.wait_for(new_started.wait(), 1)
            await asyncio.wait_for(degraded.wait(), 1)
            self.assertEqual([], cancelled)
            self.assertEqual(2, len(fetches))
            self.assertEqual(2 if mode == "episode-reset" else 1,
                             api.refresher.force_refresh_certificate.call_count)
            self.assertIsNone(adapter._reconnector._retry_task)
            finish_new.set()
            await asyncio.wait_for(updated.wait(), 1)
            for _ in range(30):
                if all(record.background_task is None for record in scheduler.task_list):
                    break
                await asyncio.sleep(0)
            self.assertEqual(1, len(scheduler.task_list))
            self.assertIsNone(scheduler.task_list[0].background_task)
            connector.connect.assert_not_awaited()
            connector.disconnect.assert_not_awaited()
            api.logout.assert_not_awaited()
            await adapter.close()
            await asyncio.sleep(0)
            self.assertEqual([], unhandled)
        finally:
            old_failure.set()
            finish_new.set()
            await adapter.close()
            await scheduler.stop()
            loop.set_exception_handler(previous)

    async def test_real_deferred_certificate_failure_cannot_cancel_a_new_worker(self):
        await self.stale_certificate_failure("deferred")

    async def test_real_cancelled_certificate_cleanup_cannot_cancel_its_successor(self):
        await self.stale_certificate_failure("cancellation")

    async def test_real_certificate_failure_cannot_cross_episode_reset(self):
        await self.stale_certificate_failure("episode-reset")

    def sso_fixture(self):
        # Check isolation before creating actual SSO state or replacing providers.
        for kind, variable in (("net", "PLASMA_VPN_TEST_NAMESPACE_PARENT"),
                               ("user", "PLASMA_VPN_TEST_USER_NAMESPACE_PARENT")):
            parent = os.environ.get(variable)
            self.assertIsNotNone(parent)
            self.assertNotEqual(parent, os.readlink(f"/proc/self/ns/{kind}"))
        from proton.sso import ProtonSSO
        from proton.keyring import Keyring
        from proton.keyring.textfile import KeyringBackendJsonFiles
        from proton.loader.loader import Loader
        from proton.utils import ExecutionEnvironment
        from proton.utils.environment import VPNExecutionEnvironment
        api_module = importlib.import_module("proton.vpn.core.api")
        holder_module = importlib.import_module("proton.vpn.core.session_holder")
        real_api = api_module.ProtonVPNAPI
        root = Path(self.enterContext(tempfile.TemporaryDirectory(dir=self.environment_root)))
        for environment, label in ((ExecutionEnvironment(), "sso"),
                                   (VPNExecutionEnvironment(), "vpn")):
            for kind in ("config", "cache", "runtime"):
                directory = root / label / kind
                directory.mkdir(parents=True, mode=0o700)
                self.enterContext(patch.object(environment, f"_path_{kind}", str(directory)))
        self.enterContext(patch.dict(os.environ, {"PROTON_LOADER_OVERRIDES": ""}))

        def account_key(name):
            return "proton-sso-account-" + base64.b32encode(name.encode()).decode().rstrip("=").lower()

        # Real JSON backend, but synthetic account data in private test storage.
        legacy = KeyringBackendJsonFiles()
        legacy["proton-sso-accounts"] = ["legacy"]
        legacy[account_key("legacy")] = {"AccountName": "legacy", "UID": "offline-legacy", "Scopes": []}
        secure = {"proton-sso-accounts": ["secure"],
                  account_key("secure"): {"AccountName": "secure", "UID": "offline-secure", "Scopes": []}}
        available = [False]
        secret_reads = []

        class SyntheticSecretService(Keyring):
            @classmethod
            def _get_priority(cls):
                return 5

            @classmethod
            def _validate(cls):
                return available[0]

            def _get_item(self, key):
                secret_reads.append(key)
                return secure[key]

        loader = Loader()
        groups = dict(loader._proton_entry_point_groups)
        groups["proton_loader_keyring"] = [
            SimpleNamespace(name="secret_service", load=lambda: SyntheticSecretService),
            SimpleNamespace(name="legacy_file", load=lambda: KeyringBackendJsonFiles),
        ]
        self.enterContext(patch.object(loader, "_Loader__known_types", {}))
        self.enterContext(patch.object(Loader, "_proton_entry_point_groups",
                                      new_callable=PropertyMock, return_value=groups))
        json_read = self.enterContext(patch.object(
            KeyringBackendJsonFiles, "_get_item", side_effect=AssertionError("JSON reads forbidden")))
        json_write = self.enterContext(patch.object(
            KeyringBackendJsonFiles, "_set_item", side_effect=AssertionError("JSON writes forbidden")))
        self.addCleanup(json_read.assert_not_called)
        self.addCleanup(json_write.assert_not_called)
        facades = []
        before_creation = Mock()

        def create_api(metadata):
            before_creation()
            # Use the real session holder, SSO, VPN session and logged-in getter;
            # substitute API construction and stop at the networking boundary.
            facade = object.__new__(real_api)
            facade._session_holder = holder_module.SessionHolder(metadata)
            self.addCleanup(facade._session_holder._proton_sso._global_adv_lock.close)
            facade.refresher = adapter_tests.ProtonCoreAdapterTests().make_api()[0].refresher
            facade.get_vpn_connector = AsyncMock(side_effect=RetirementRejected("No networking in fixture"))
            facades.append(facade)
            return facade

        factory = self.enterContext(patch.object(api_module, "ProtonVPNAPI", side_effect=create_api))
        adapter = ProtonCoreAdapter(account_transition_path=root / "account.json")
        self.addAsyncCleanup(adapter.close)
        return SimpleNamespace(adapter=adapter, factory=factory, facades=facades,
                               available=available, secret_reads=secret_reads,
                               secret_data=secure,
                               before_creation=before_creation, sso=ProtonSSO,
                               keyring=Keyring, secret_type=SyntheticSecretService,
                               account_key=account_key)

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    async def test_actual_sso_cached_json_success_cannot_bypass_admission(self):
        fixture = self.sso_fixture()
        entered, release = asyncio.Event(), asyncio.Event()
        async def wait(_remaining, *, initial_admission, request_unlock):
            self.assertTrue(initial_admission)
            self.assertTrue(request_unlock)
            entered.set()
            await release.wait()
            return True
        snapshots = []
        with patch("proton_vpn_kde_backend.adapters.wait_for_secret_service",
                   new=AsyncMock(side_effect=wait)):
            task = asyncio.create_task(fixture.adapter.initialize(snapshots.append))
            await asyncio.wait_for(entered.wait(), 1)
            fixture.factory.assert_not_called()
            self.assertEqual([], fixture.secret_reads)
            self.assertFalse(snapshots[-1].ready)
            fixture.available[0] = True
            release.set()
            with self.assertRaises(ConnectorStartupError) as caught:
                await asyncio.wait_for(task, 1)
        self.assertTrue(caught.exception.logged_in)
        self.assertIsInstance(caught.exception.__cause__, RetirementRejected)
        self.assertEqual("secure", fixture.facades[0].account_name)
        fixture.factory.assert_called_once()
        fixture.facades[0].get_vpn_connector.assert_awaited_once()
        self.assertTrue(fixture.secret_reads)
        self.assertIn("keyring=secret_service", os.environ["PROTON_LOADER_OVERRIDES"].split())
        fixture.available[0] = False
        with self.assertRaises(RuntimeError):
            fixture.facades[0]._session_holder._proton_sso._get_session_data("secure")

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    async def test_actual_loader_provider_loss_before_lookup_never_selects_json(self):
        fixture = self.sso_fixture()
        fixture.available[0] = True
        def lose_provider():
            fixture.available[0] = False
        fixture.before_creation.side_effect = lose_provider
        controller = BackendController(fixture.adapter)
        with patch("proton_vpn_kde_backend.adapters.wait_for_secret_service",
                   new=AsyncMock(return_value=True)), \
             self.assertLogs("proton_vpn_kde_backend.controller", level="ERROR"):
            self.assertFalse(await controller.start())
        self.assertEqual([], fixture.secret_reads)
        fixture.facades[0].get_vpn_connector.assert_not_awaited()
        self.assertFalse(fixture.adapter._initialized)
        self.assertFalse(controller.snapshot.ready)
        self.assertEqual("authentication_unknown", controller.snapshot.auth_state)

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    async def test_actual_sso_rechecks_cannot_fall_back_after_provider_loss(self):
        fixture = self.sso_fixture()
        require_secret_service_backend()
        fixture.available[0] = True
        sso = fixture.sso(appversion="offline-fixture@0")
        self.addCleanup(sso._global_adv_lock.close)
        session = sso.get_default_session(override_class=importlib.import_module("proton.vpn.session").VPNSession)
        self.assertTrue(session.logged_in)
        self.assertEqual("secure", session.AccountName)
        fixture.available[0] = False
        with self.assertRaises(RuntimeError):
            sso._get_session_data("secure")
        with self.assertRaises(RuntimeError):
            fixture.keyring.get_from_factory()[fixture.account_key("secure")] = {"AccountName": "unused"}
        fixture.available[0] = True
        self.assertEqual("secure", sso._get_session_data("secure")["AccountName"])
        self.assertIsInstance(sso._keyring, fixture.secret_type)

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    def test_secret_service_selector_matches_installed_keyring_registration(self):
        from importlib.metadata import entry_points
        self.assertTrue(any(entry.name == "secret_service" for entry in entry_points(
            group="proton_loader_keyring")))

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    async def test_actual_sso_empty_secret_store_does_not_restore_legacy_json_session(self):
        fixture = self.sso_fixture()
        fixture.secret_data.clear()
        from dbus_fast import Variant
        from dbus_fast.constants import MessageType
        owner, observed = ":1.42", []
        async def call(message):
            observed.append(message.member)
            if message.member == "StartServiceByName":
                self.assertEqual(["org.freedesktop.secrets", 0], message.body)
                fixture.available[0] = True
                body = [1]
            elif message.member == "GetNameOwner":
                body = [owner]
            elif message.member == "GetConnectionUnixUser":
                body = [os.getuid()]
            elif message.member == "ReadAlias":
                body = ["/"]
            elif message.member == "Get":
                self.assertEqual(["org.freedesktop.Secret.Service", "Collections"], message.body)
                body = [Variant("ao", [])]
            else:
                raise AssertionError("Admission must not create a collection or read secrets")
            return SimpleNamespace(body=body, sender=owner, message_type=MessageType.METHOD_RETURN)
        bus = SimpleNamespace(connect=AsyncMock(), call=AsyncMock(side_effect=call),
                              disconnect=Mock(), wait_for_disconnect=AsyncMock())
        with patch("proton_vpn_kde_backend.secret_service_readiness.MessageBus", return_value=bus):
            with self.assertRaises(ConnectorStartupError) as caught:
                await fixture.adapter.initialize(lambda _snapshot: None)
        self.assertFalse(caught.exception.logged_in)
        self.assertIsInstance(caught.exception.__cause__, RetirementRejected)
        self.assertEqual("StartServiceByName", observed[0])
        fixture.factory.assert_called_once()
        self.assertIsNone(fixture.facades[0].account_name)
        self.assertIsInstance(fixture.facades[0]._session_holder._proton_sso._keyring, fixture.secret_type)
        self.assertEqual("keyring=secret_service", os.environ["PROTON_LOADER_OVERRIDES"])

    async def prompt_admission(self, outcome):
        from test_secret_service_unlock import FakeUnlockBus
        fixture = self.sso_fixture()
        fixture.available[0] = True
        bus = FakeUnlockBus("pending")
        bus.alias = "/"  # Exercise the actual SSO gate without a default alias.
        controller = BackendController(fixture.adapter)
        with patch("proton_vpn_kde_backend.secret_service_readiness.MessageBus", return_value=bus), \
             patch("proton_vpn_kde_backend.adapters.SECRET_STORE_WAIT_SECONDS",
                   0.03 if outcome == "timeout" else 5), \
             self.assertLogs("proton_vpn_kde_backend.controller", level="ERROR"):
            task = asyncio.create_task(controller.start())
            await asyncio.wait_for(bus.shown.wait(), 1)
            fixture.factory.assert_not_called()
            self.assertEqual([], fixture.secret_reads)
            self.assertEqual("keyring=secret_service", os.environ["PROTON_LOADER_OVERRIDES"])
            self.assertFalse(controller.snapshot.ready)
            if outcome != "timeout":
                bus.complete(dismissed=outcome == "dismissed")
            self.assertFalse(await asyncio.wait_for(task, 1))
        if outcome == "success":
            fixture.factory.assert_called_once()
            self.assertTrue(controller.snapshot.logged_in)
            self.assertEqual("secure", fixture.facades[0].account_name)
            fixture.facades[0].get_vpn_connector.assert_awaited_once()
            self.assertEqual("connector_initialization_failed", controller.snapshot.error_code)
        else:
            fixture.factory.assert_not_called()
            self.assertEqual("authentication_unknown", controller.snapshot.auth_state)
            self.assertEqual("secret_store_locked", controller.snapshot.error_code)
        self.assertEqual(1, len(bus.members("Unlock")))
        self.assertEqual(int(outcome == "timeout"), len(bus.members("Dismiss")))
        self.assertEqual([], bus.handlers)

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    async def test_actual_sso_waits_for_provider_prompt_before_session_lookup(self):
        await self.prompt_admission("success")

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    async def test_actual_sso_prompt_dismissal_never_restores_from_json(self):
        await self.prompt_admission("dismissed")

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    async def test_actual_sso_prompt_timeout_never_restores_from_json(self):
        await self.prompt_admission("timeout")

    @unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_SSO_SITE_PACKAGES"),
                         "explicit hash-checked SSO fixture required")
    async def test_actual_sso_prompt_cancellation_cannot_start_late_session_lookup(self):
        from test_secret_service_unlock import FakeUnlockBus
        fixture = self.sso_fixture()
        fixture.available[0] = True
        bus = FakeUnlockBus("pending")
        with patch("proton_vpn_kde_backend.secret_service_readiness.MessageBus", return_value=bus):
            task = asyncio.create_task(fixture.adapter.initialize(lambda _snapshot: None))
            await asyncio.wait_for(bus.shown.wait(), 1)
            fixture.factory.assert_not_called()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        bus.complete()
        fixture.factory.assert_not_called()
        self.assertEqual([], fixture.secret_reads)
        self.assertEqual(1, len(bus.members("Dismiss")))
        self.assertEqual([], bus.handlers)
