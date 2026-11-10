# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Offline selection and retry policy; no accounts, routes, or real buses."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core_fakes import ServerFeatureEnum as Feature, ServerNotFoundError, core_module_fakes
from proton_vpn_kde_backend.core_servers import FastestSelection
from proton_vpn_kde_backend.errors import UserVisibleValueError
from proton_vpn_kde_backend.reconnector import AsyncReconnector


DEFAULT_SELECTION = FastestSelection()


def error_state(event_name="Timeout"):
    return type("Error", (), {
        "context": SimpleNamespace(event=type(event_name, (), {})()),
    })()


def server(identifier, *, features=Feature.P2P | Feature.STREAMING, **kwargs):
    return SimpleNamespace(
        id=identifier, features=[features], enabled=kwargs.get("enabled", True),
        tier=kwargs.get("tier", 1), score=kwargs.get("score", 1),
        exit_country=kwargs.get("country", "CH"),
        location=kwargs.get("location", "Zurich"),
    )


class Catalog:
    """Small enumerable model of Core's public availability/filter/rank API."""

    def __init__(self, servers=None, *, logicals=None, user_tier=2, index_servers=True):
        self.logicals = list(servers if servers is not None else logicals)
        self.user_tier = user_tier
        self._by_id = {s.id: s for s in self.logicals} if index_servers else {}

    def get_by_id(self, identifier):
        try:
            return self._by_id[identifier]
        except KeyError:
            raise ServerNotFoundError(identifier) from None

    def get_available_servers(self, servers, tier):
        return (s for s in servers if s.enabled and s.tier <= tier)

    def get_servers_with_features(self, servers, *, request_features, exclude_features):
        return (s for s in servers if s.features[0] & request_features == request_features
                and not s.features[0] & exclude_features)

    def get_fastest_server(self, servers):
        return min(servers, key=lambda s: s.score, default=None)

    def get_servers_in_country_code(self, servers, code):
        return (s for s in servers if s.exit_country.upper() == code.upper())

    def group_by_country(self, *, include_free_servers=True, **_kwargs):
        countries = []
        for code in sorted({s.exit_country for s in self.logicals}):
            selected = [s for s in self.logicals if s.exit_country == code]
            ordinary = [s for s in selected if not s.features[0] & Feature.SECURE_CORE
                        and (include_free_servers or s.tier != 0)]
            secure = [s for s in selected if s.features[0] & Feature.SECURE_CORE]
            countries.append(SimpleNamespace(
                code=code, servers=selected,
                locations=[SimpleNamespace(name=name, servers=[s for s in ordinary if s.location == name])
                           for name in sorted({s.location for s in ordinary})],
                secure_core_group=(SimpleNamespace(name="Via Secure Core", servers=secure)
                                   if secure else None),
            ))
        return countries


def selection_core_fakes():
    modules = core_module_fakes()
    modules["proton.vpn.session.servers"].ServerList = Catalog
    return modules


@patch.dict("sys.modules", selection_core_fakes())
class FastestSelectionTests(unittest.TestCase):
    def test_intersection_tier_and_maintenance_are_never_relaxed(self):
        servers = [
            server("original"), server("p2p-only", features=Feature.P2P),
            server("paid", tier=3), server("maintenance", enabled=False),
            server("eligible", score=4),
        ]
        catalog = Catalog(servers)
        selection = FastestSelection(features=("p2p", "streaming"))
        self.assertEqual("eligible", selection.pick(catalog, "", {"original"}).id)
        self.assertIsNone(selection.pick(catalog, "", {"original", "eligible"}))

    def test_ordinary_fastest_retains_core_special_mode_exclusions(self):
        catalog = Catalog([
            server("tor", features=Feature.TOR),
            server("secure", features=Feature.SECURE_CORE), server("normal", score=5),
        ])
        self.assertEqual("normal", FastestSelection().pick(catalog, "", set()).id)
        self.assertEqual("secure", FastestSelection(features=("secure-core",)).pick(
            catalog, "", set()).id)
        self.assertEqual("tor", FastestSelection(features=()).pick(catalog, "", set()).id)

    def test_eligible_current_server_is_preferred_over_a_faster_server(self):
        catalog = Catalog([server("current", score=10), server("faster", score=1)])
        self.assertEqual("current", FastestSelection().pick(catalog, "current", set()).id)

    def test_country_and_group_scopes_survive_failover(self):
        catalog = Catalog([
            server("original"), server("same-location", score=5),
            server("same-country", score=2, location="Geneva"),
            server("other-country", country="US", score=0),
        ])
        selections = (
            (FastestSelection(country_code="CH"), "same-country"),
            (FastestSelection(country_code="CH", features=("p2p",)), "same-country"),
            (FastestSelection(country_code="CH", group_kind="location",
                              group_name="Zurich", features=()), "same-location"),
        )
        for selection, expected in selections:
            with self.subTest(selection=selection):
                self.assertEqual(expected, selection.pick(catalog, "", {"original"}).id)

    def test_secure_core_group_does_not_fall_back_to_an_ordinary_group(self):
        secure = server("secure", features=Feature.SECURE_CORE | Feature.P2P)
        catalog = Catalog([server("ordinary"), secure])
        selection = FastestSelection(
            country_code="CH", group_kind="secure-core", group_name="Via Secure Core",
            features=("secure-core", "p2p"),
        )
        self.assertIs(secure, selection.pick(catalog, "", set()))
        secure.enabled = False
        self.assertIsNone(selection.pick(catalog, "", set()))
        secure.features = [Feature.P2P]
        with self.assertRaises(UserVisibleValueError):
            selection.pick(catalog, "", set())

    def test_preferred_lookup_never_enumerates_the_catalog(self):
        class NoIteration(list):
            def __iter__(self):
                raise AssertionError("Preferred retry enumerated the catalog")

        preferred = server("current")
        catalog = Catalog([preferred, server("other", country="US")])
        catalog.logicals = NoIteration(catalog.logicals)
        for selection in (
            FastestSelection(), FastestSelection(country_code="CH"),
            FastestSelection(country_code="CH", features=("p2p", "streaming")),
            FastestSelection(country_code="CH", group_kind="location",
                             group_name="Zurich", features=()),
        ):
            with self.subTest(selection=selection):
                self.assertIs(preferred, selection.pick(catalog, "current", set()))

    def test_group_projection_is_limited_to_the_selected_country(self):
        catalog = Catalog([server("original"), server("replacement")]
                          + [server(str(i), country="US") for i in range(1000)])
        sizes = []
        group = Catalog.group_by_country

        def measured(view, **kwargs):
            sizes.append(len(view.logicals))
            return group(view, **kwargs)

        selection = FastestSelection(country_code="CH", group_kind="location",
                                     group_name="Zurich", features=("p2p",))
        with patch.object(Catalog, "group_by_country", measured):
            self.assertEqual("replacement", selection.pick(catalog, "", {"original"}).id)
        self.assertEqual([2], sizes)

    def test_preferred_rechecks_scope_features_tier_and_maintenance(self):
        selection = FastestSelection(country_code="CH", group_kind="location",
                                     group_name="Zurich", features=("p2p", "streaming"))
        for change in (
            {"exit_country": "US"}, {"location": "Geneva"},
            {"features": [Feature.P2P]}, {"tier": 3}, {"enabled": False},
        ):
            with self.subTest(change=change):
                preferred = server("current")
                preferred.__dict__.update(change)
                catalog = Catalog([preferred, server("replacement", score=9)])
                self.assertIsNone(selection.pick(catalog, "current", set(), only_preferred=True))
                self.assertEqual("replacement", selection.pick(catalog, "current", set()).id)

    def test_missing_preferred_and_exclusions_do_not_relax_scope(self):
        catalog = Catalog([server("ch"), server("us", country="US", score=0)])
        selection = FastestSelection(country_code="CH")
        self.assertIsNone(selection.pick(catalog, "removed", set(), only_preferred=True))
        self.assertEqual("ch", selection.pick(catalog, "removed", set()).id)
        self.assertIsNone(selection.pick(catalog, "ch", {"ch"}))


@patch.dict("sys.modules", selection_core_fakes())
class FastestFailoverTests(unittest.IsolatedAsyncioTestCase):
    def make_reconnector(self, *, selection=DEFAULT_SELECTION, servers=None):
        catalog = Catalog(servers if servers is not None else [
            server("a", score=1), server("b", score=2),
            server("c", score=3), server("d", score=4),
        ])
        connector = SimpleNamespace(
            current_connection=SimpleNamespace(server_id="a", protocol="smart", backend="nm"),
            current_state=error_state(), register=Mock(), unregister=Mock(),
            get_vpn_server=Mock(side_effect=lambda logical, _config: logical),
            connect=AsyncMock(side_effect=AssertionError("Policy cannot call Core Up")),
            disconnect=AsyncMock(side_effect=AssertionError("Policy cannot remove protection")),
        )
        attempt = AsyncMock(return_value=True)
        messages = []
        probe = SimpleNamespace(is_unlocked=AsyncMock(return_value=True), close=AsyncMock())
        reconnector = AsyncReconnector(
            connector, SimpleNamespace(server_list=catalog, client_config="config",
                                       force_refresh_certificate=Mock()), messages.append,
            connection_attempt=attempt, authentication_epoch_source=lambda: 7,
            authentication_epoch_validator=lambda epoch: epoch == 7,
            authentication_error_callback=AsyncMock(), session_probe=probe,
            fastest_selection_source=lambda: selection,
        )
        # Drive retry ticks explicitly so neither wall-clock timers nor a real
        # connection can decide test order. All dispatch still uses its owner.
        reconnector._enabled = True
        self.addAsyncCleanup(reconnector.disable)
        self.addCleanup(connector.connect.assert_not_awaited)
        self.addCleanup(connector.disconnect.assert_not_awaited)
        return reconnector, connector, catalog, attempt, probe, messages

    async def retry(self, reconnector, count=1):
        for _ in range(count):
            await reconnector._attempt_retry(reconnector._retry_generation)

    async def test_two_retries_then_at_most_two_alternatives_with_existing_owner(self):
        reconnector, _, _, attempt, _, messages = self.make_reconnector()
        await self.retry(reconnector, 10)
        self.assertEqual(["a", "a", "b", "b", "c", "c", "c", "c", "c", "c"],
                         [call.args[0].id for call in attempt.await_args_list])
        for call in attempt.await_args_list:
            self.assertEqual(("smart", "nm", 7), call.args[1:])
        self.assertEqual({"a", "b"}, reconnector._failover_excluded)
        self.assertEqual(2, reconnector._failover_attempts)
        self.assertEqual(2, messages.count("Trying another server matching your Fastest selection…"))

    async def test_no_alternative_keeps_retrying_the_eligible_original(self):
        reconnector, _, _, attempt, _, _ = self.make_reconnector(servers=[server("a")])
        await self.retry(reconnector, 6)
        self.assertEqual(["a"] * 6, [call.args[0].id for call in attempt.await_args_list])
        self.assertFalse(reconnector._failover_excluded)

    async def test_explicit_or_unknown_selection_never_changes_server(self):
        reconnector, _, _, attempt, _, _ = self.make_reconnector(selection=None)
        await self.retry(reconnector, 8)
        self.assertEqual(["a"] * 8, [call.args[0].id for call in attempt.await_args_list])
        self.assertIsNone(reconnector._failover_server_id)

    async def test_exhausted_budget_waits_rather_than_using_a_fourth_server(self):
        reconnector, _, catalog, attempt, _, messages = self.make_reconnector()
        await self.retry(reconnector, 5)
        catalog.get_by_id("c").enabled = False
        await self.retry(reconnector, 3)
        self.assertEqual(5, attempt.await_count)
        self.assertIn("Waiting for a server matching your Fastest selection…", messages)
        catalog.get_by_id("c").enabled = True
        await self.retry(reconnector)
        self.assertEqual("c", attempt.await_args.args[0].id)

    async def test_no_filter_match_waits_without_unfiltered_connection(self):
        reconnector, _, _, attempt, _, messages = self.make_reconnector(
            selection=FastestSelection(features=("tor", "p2p")),
        )
        await self.retry(reconnector, 4)
        attempt.assert_not_awaited()
        self.assertTrue(all("matching your Fastest selection" in message for message in messages))

    async def test_failover_dispatch_keeps_location_and_feature_intersection(self):
        reconnector, _, catalog, attempt, _, _ = self.make_reconnector(
            selection=FastestSelection(features=("p2p", "streaming"), country_code="CH",
                                       group_kind="location", group_name="Zurich"),
        )
        catalog.get_by_id("b").features = [Feature.P2P]
        catalog.get_by_id("d").location = "Geneva"
        await self.retry(reconnector, 5)
        self.assertEqual(["a", "a", "c", "c", "c"],
                         [call.args[0].id for call in attempt.await_args_list])

    async def test_availability_and_features_are_rechecked_from_current_cache(self):
        reconnector, _, catalog, attempt, _, _ = self.make_reconnector(
            selection=FastestSelection(features=("p2p", "streaming")),
        )
        await self.retry(reconnector)
        catalog.get_by_id("a").features = [Feature.P2P]
        catalog.get_by_id("b").tier = 3
        catalog.get_by_id("c").enabled = False
        await self.retry(reconnector)
        self.assertEqual(["a", "d"], [call.args[0].id for call in attempt.await_args_list])

    async def test_removed_location_never_becomes_global_fastest(self):
        reconnector, _, catalog, attempt, _, _ = self.make_reconnector(
            selection=FastestSelection(country_code="CH", group_kind="location",
                                       group_name="Zurich", features=()),
        )
        for logical in catalog.logicals:
            logical.location = "Geneva"
        with self.assertLogs("proton_vpn_kde_backend.reconnector", level="ERROR"):
            await self.retry(reconnector, 2)
        attempt.assert_not_awaited()

    async def test_missing_previous_connection_does_not_spend_failover_budget(self):
        reconnector, connector, _, attempt, _, _ = self.make_reconnector()
        connection = connector.current_connection
        connector.current_connection = None
        await self.retry(reconnector, 4)
        attempt.assert_not_awaited()
        connector.current_connection = connection
        await self.retry(reconnector, 3)
        self.assertEqual(["a", "a", "b"], [call.args[0].id for call in attempt.await_args_list])

    async def test_locked_session_does_not_spend_failover_attempts(self):
        reconnector, _, _, attempt, probe, _ = self.make_reconnector()
        probe.is_unlocked.return_value = False
        await self.retry(reconnector, 5)
        attempt.assert_not_awaited()
        probe.is_unlocked.return_value = True
        await self.retry(reconnector, 3)
        self.assertEqual(["a", "a", "b"], [call.args[0].id for call in attempt.await_args_list])

    async def test_non_network_errors_do_not_trigger_roaming(self):
        reconnector, connector, _, attempt, _, _ = self.make_reconnector()
        connector.current_state = error_state("FeaturePolicyError")
        await self.retry(reconnector, 6)
        self.assertEqual(["a"] * 6, [call.args[0].id for call in attempt.await_args_list])

    async def test_connected_resets_budget_without_forgetting_selection(self):
        reconnector, connector, _, attempt, _, _ = self.make_reconnector()
        await self.retry(reconnector, 5)
        connector.current_connection.server_id = "c"
        connector.current_state = type("Connected", (), {})()
        reconnector.status_update(connector.current_state)
        connector.current_state = error_state()
        await self.retry(reconnector, 3)
        self.assertEqual(["c", "c", "a"],
                         [call.args[0].id for call in attempt.await_args_list[-3:]])

    async def test_retired_account_cannot_dispatch_a_new_candidate(self):
        reconnector, _, _, attempt, _, _ = self.make_reconnector()
        await self.retry(reconnector, 2)
        reconnector._authentication_epoch_validator = lambda _epoch: False
        await self.retry(reconnector)
        self.assertEqual(2, attempt.await_count)

    async def test_suspension_preserves_episode_and_backoff(self):
        reconnector, connector, _, attempt, _, _ = self.make_reconnector()
        reconnector._delay_factory = lambda _counter: 60
        await self.retry(reconnector, 5)
        connector.current_connection.server_id = "c"
        before = (reconnector.retry_counter, reconnector._failover_server_id,
                  reconnector._failover_attempts, set(reconnector._failover_excluded))
        async with reconnector.suspended():
            self.assertEqual(before, (
                reconnector.retry_counter, reconnector._failover_server_id,
                reconnector._failover_attempts, set(reconnector._failover_excluded),
            ))
        await self.retry(reconnector, 3)
        self.assertEqual(["a", "a", "b", "b", "c", "c", "c", "c"],
                         [call.args[0].id for call in attempt.await_args_list])

    async def test_switch_tick_projects_once_and_exhaustion_does_not_enumerate(self):
        reconnector, _, catalog, attempt, _, _ = self.make_reconnector(
            selection=FastestSelection(country_code="CH", group_kind="location",
                                       group_name="Zurich", features=()),
        )
        await self.retry(reconnector, 2)
        sizes = []
        group = Catalog.group_by_country

        def measured(view, **kwargs):
            sizes.append(len(view.logicals))
            return group(view, **kwargs)

        with patch.object(Catalog, "group_by_country", measured):
            await self.retry(reconnector)
        self.assertEqual([4], sizes)
        await self.retry(reconnector, 2)
        catalog.get_by_id("c").enabled = False
        with patch.object(catalog, "get_fastest_server", side_effect=AssertionError("Budget spent")):
            await self.retry(reconnector, 2)
        self.assertEqual(5, attempt.await_count)
