# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import gc
import importlib.util
import json
import math
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from core_fakes import core_module_fakes
from proton_vpn_kde_backend.adapters import ProtonCoreAdapter
from proton_vpn_kde_backend.search_projection import ServerSearchProjection


class StubServer:
    def __init__(
        self,
        name: str,
        country: str,
        location: str,
        load: int,
        *,
        enabled: bool = True,
        tier: int = 2,
        secure_core: bool = False,
    ):
        self.name = name
        self.exit_country = country
        self.exit_country_name = country
        self.location = location
        self.load = load
        self.enabled = enabled
        self.tier = tier
        self.features = {"secure-core"} if secure_core else set()

    @property
    def under_maintenance(self) -> bool:
        return not self.enabled


class StubServerList:
    def __init__(self, servers: list[StubServer], user_tier: int = 2):
        self.logicals = servers
        self.user_tier = user_tier
        self._by_name = {server.name.upper(): server for server in servers}

    def get_by_name(self, name: str) -> StubServer:
        return self._by_name[name.upper()]

    @staticmethod
    def get_available_servers(servers, user_tier):
        return (
            server for server in servers if server.enabled and server.tier <= user_tier
        )


def sort_key(server: StubServer) -> str:
    prefix, _, suffix = server.name.lower().partition("#")
    natural_name = f"{prefix}#{suffix.zfill(10)}" if suffix else prefix
    return f"{server.exit_country_name}__{natural_name}"


class OfflineSearchBenchmarkTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_measurement_passes_use_offline_authenticated_fixture(self):
        modules = core_module_fakes()
        cache_module = ModuleType("proton.vpn.core.cache_handler")
        fetcher_module = ModuleType("proton.vpn.session.servers.server_list_fetcher")

        class CacheHandler:
            def __init__(self, path, *, object_hook_factory):
                self.path = path

            def load(self):
                return json.loads(self.path.read_text())

        def from_dict(payload):
            return StubServerList([
                StubServer(row["Name"], row["ExitCountry"], row["City"], row["Load"])
                for row in payload["LogicalServers"]
            ], payload["MaxTier"])

        cache_module.CacheHandler = CacheHandler
        fetcher_module.ServerListFetcher = SimpleNamespace(CACHE_PATH=Path("not-used"))
        logicals = modules["proton.vpn.session.servers.logicals"]
        logicals.ServerList = SimpleNamespace(from_dict=from_dict)
        logicals._server_string_object_hook = lambda: lambda item: item
        modules[cache_module.__name__] = cache_module
        modules[fetcher_module.__name__] = fetcher_module
        script = Path(__file__).resolve().parents[2] / "scripts/benchmark-search.py"
        spec = importlib.util.spec_from_file_location("offline_search_benchmark", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", modules):
            cache = Path(directory) / "serverlist.json"
            cache.write_text(json.dumps({"MaxTier": 2, "LogicalServers": [
                {"Name": "CH#1", "ExitCountry": "CH", "City": "Zürich", "Load": 10},
                {"Name": "US#1", "ExitCountry": "US", "City": "New York", "Load": 20},
            ]}))
            spec.loader.exec_module(module)
            with (
                patch.object(module, "_offline_search_adapter", wraps=module._offline_search_adapter) as factory,
                patch.object(ProtonCoreAdapter, "initialize", side_effect=AssertionError("No session initialization")),
                patch.object(ProtonCoreAdapter, "login", side_effect=AssertionError("No authentication")),
                patch("socket.socket", side_effect=AssertionError("No network")),
            ):
                report = await module.benchmark(cache, 2, ["zur", "us-", "notfound"])
            self.assertEqual(factory.call_count, 2)  # Timing AND allocation adapters.
            self.assertEqual(report["logicalServerCount"], 2)
            self.assertEqual(report["projectedLocationCount"], 2)
            self.assertEqual(report["projectedServerCount"], 2)
            self.assertEqual(report["queries"][0]["resultCounts"], {"location": 1})
            self.assertEqual(report["queries"][-1]["resultCounts"], {})
            self.assertGreaterEqual(report["projectionPeakBuildBytes"], report["projectionCurrentBytes"])
            for value in report.values():
                if isinstance(value, (int, float)):
                    self.assertTrue(math.isfinite(value) and value >= 0)
            for query in report["queries"]:
                for key in ("medianMilliseconds", "p95Milliseconds", "maximumMilliseconds"):
                    self.assertTrue(math.isfinite(query[key]) and query[key] >= 0)


class ServerSearchProjectionTests(unittest.TestCase):
    def make_projection(self, server_list: StubServerList):
        return ServerSearchProjection.build(
            server_list,
            generation=7,
            secure_core_feature="secure-core",
            server_sort_key=sort_key,
        )

    def test_search_preserves_location_server_and_secure_core_results(self):
        servers = StubServerList(
            [
                StubServer("CH#10", "CH", "Zürich", 42),
                StubServer("CH#2", "CH", "Zürich", 21),
                StubServer("CH-DE#1", "CH", "Zürich", 35, secure_core=True),
                StubServer("US#1", "US", "New York", 5, tier=3),
            ]
        )
        projection = self.make_projection(servers)

        location_results = projection.search(servers, "zur")
        server_results = projection.search(servers, "ch#")
        secure_core_results = projection.search(servers, "ch-de")

        self.assertEqual(["Zürich"], [item.name for item in location_results])
        self.assertEqual(["CH#2", "CH#10"], [item.name for item in server_results])
        self.assertEqual("secure-core", secure_core_results[0].group_kind)
        self.assertEqual("Via Secure Core", secure_core_results[0].group_name)

    def test_load_and_availability_changes_do_not_require_a_rebuild(self):
        server = StubServer("CH#10", "CH", "Zürich", 42)
        servers = StubServerList([server])
        projection = self.make_projection(servers)

        self.assertEqual(42, projection.search(servers, "ch#")[0].load)
        server.load = 7
        self.assertEqual(7, projection.search(servers, "ch#")[0].load)
        server.enabled = False
        self.assertEqual([], projection.search(servers, "ch#"))
        self.assertEqual([], projection.search(servers, "zur"))

    def test_paid_location_remains_visible_but_paid_server_is_not_connectable(self):
        paid = StubServer("US#1", "US", "New York", 5, tier=3)
        servers = StubServerList([paid], user_tier=0)
        projection = self.make_projection(servers)

        locations = projection.search(servers, "new")

        self.assertEqual(1, len(locations))
        self.assertFalse(locations[0].accessible)
        self.assertEqual([], projection.search(servers, "us#"))

    def test_projection_does_not_retain_official_server_objects(self):
        server = StubServer("CH#10", "CH", "Zürich", 42)
        server_reference = weakref.ref(server)
        servers = StubServerList([server])

        projection = self.make_projection(servers)
        self.assertEqual(1, projection.server_count)
        del servers
        del server
        gc.collect()

        self.assertIsNone(server_reference())

    def test_projection_does_not_change_official_server_order(self):
        first = StubServer("CH#10", "CH", "Zürich", 42)
        second = StubServer("CH#2", "CH", "Zürich", 21)
        servers = StubServerList([first, second])

        self.make_projection(servers)

        self.assertEqual([first, second], servers.logicals)


if __name__ == "__main__":
    unittest.main()
