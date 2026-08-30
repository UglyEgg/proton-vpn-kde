# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import gc
import unittest
import weakref

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
