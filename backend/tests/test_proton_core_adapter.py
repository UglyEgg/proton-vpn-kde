# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
from ipaddress import ip_address
import threading
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from proton_vpn_kde_backend.adapters import (
    ProtonCoreAdapter,
    _core_memory_optimization_behavior,
)
from proton_vpn_kde_backend.controller import NpsSurveyResponse, SupportReport


def state_named(name: str):
    return type(name, (), {})()


class CoreMemoryOptimizationProbeTests(unittest.TestCase):
    @staticmethod
    def optimized_module():
        def object_hook_factory():
            shared = {}

            def share(item):
                value = item.get("Domain")
                if isinstance(value, str):
                    item["Domain"] = shared.setdefault(value, value)
                return item

            return share

        def deduplicate(logicals):
            share = object_hook_factory()
            for logical in logicals:
                share(logical)
                for physical in logical.get("Servers", ()):
                    share(physical)

        return SimpleNamespace(
            _deduplicate_server_strings=deduplicate,
            _server_string_object_hook=object_hook_factory,
        )

    def test_accepts_both_verified_string_sharing_behaviors(self):
        self.assertTrue(_core_memory_optimization_behavior(self.optimized_module()))

    def test_rejects_an_unoptimized_or_partial_core(self):
        self.assertFalse(_core_memory_optimization_behavior(SimpleNamespace()))
        self.assertFalse(
            _core_memory_optimization_behavior(
                SimpleNamespace(
                    _deduplicate_server_strings=lambda logicals: None,
                    _server_string_object_hook=lambda: lambda item: item,
                )
            )
        )


class ProtonCoreAdapterTests(unittest.IsolatedAsyncioTestCase):
    def make_api(self, *, logged_in: bool = True):
        protocol = SimpleNamespace(
            protocol="wireguard",
            ui_protocol="WireGuard",
            supports_packet_capture=Mock(return_value=False),
        )
        connector = SimpleNamespace(
            current_state=state_named("Disconnected"),
            current_connection=None,
            register=Mock(),
            unregister=Mock(),
            get_vpn_server=Mock(return_value="vpn-server"),
            connect=AsyncMock(),
            disconnect=AsyncMock(),
            iter_available_protocols=Mock(return_value=[protocol]),
            is_split_tunneling_available=True,
        )
        refresher = SimpleNamespace(
            enable=AsyncMock(),
            disable=AsyncMock(),
            set_server_list_updated_callback=Mock(),
            set_server_loads_updated_callback=Mock(),
            set_location_names_updated_callback=Mock(),
            get_up_to_date_server_list=AsyncMock(),
            get_up_to_date_client_config=AsyncMock(return_value="client-config"),
            feature_flags={},
            notifications=SimpleNamespace(
                get_nps_survey_notifications=Mock(return_value=[])
            ),
        )
        exclude_config = SimpleNamespace(
            app_paths=["/usr/bin/firefox"],
            ip_ranges=["10.0.0.0/8"],
        )
        include_config = SimpleNamespace(app_paths=[], ip_ranges=[])
        split_tunneling = SimpleNamespace(
            enabled=False,
            mode=SimpleNamespace(value="exclude"),
            exclude=exclude_config,
            include=include_config,
        )
        split_tunneling.get_config = Mock(
            side_effect=lambda: (
                split_tunneling.exclude
                if getattr(split_tunneling.mode, "value", split_tunneling.mode)
                == "exclude"
                else split_tunneling.include
            )
        )
        settings = SimpleNamespace(
            protocol="wireguard",
            killswitch=0,
            custom_dns=SimpleNamespace(
                enabled=False,
                ip_list=[
                    SimpleNamespace(
                        ip=ip_address("9.9.9.9"),
                        enabled=False,
                    )
                ],
            ),
            ipv6=True,
            anonymous_crash_reports=False,
            features=SimpleNamespace(
                netshield=1,
                moderate_nat=False,
                vpn_accelerator=True,
                port_forwarding=False,
                split_tunneling=split_tunneling,
            ),
        )
        api = SimpleNamespace(
            get_vpn_connector=AsyncMock(return_value=connector),
            validate_connection_availability=Mock(return_value=True),
            is_user_logged_in=Mock(return_value=logged_in),
            account_name="test-user",
            account_data=SimpleNamespace(
                plan_title="VPN Plus",
                max_tier=2,
                max_connections=10,
            ),
            supports_fido2=False,
            refresher=refresher,
            login=AsyncMock(),
            submit_2fa_code=AsyncMock(),
            generate_2fa_fido2_assertion=AsyncMock(),
            submit_2fa_fido2=AsyncMock(),
            logout=AsyncMock(),
            submit_bug_report=AsyncMock(),
            submit_nps_response=AsyncMock(),
            set_notification_seen=Mock(),
            load_settings=AsyncMock(return_value=settings),
            save_settings=AsyncMock(),
            usage_reporting=SimpleNamespace(enabled=False),
        )
        return api, connector

    async def test_startup_compatibility_uses_official_core_check(self):
        api, _ = self.make_api()
        api.validate_connection_availability.return_value = False
        adapter = ProtonCoreAdapter(api)

        snapshot = await adapter.initialize(Mock())

        self.assertFalse(snapshot.startup_compatible)
        api.validate_connection_availability.assert_called_once_with()

    async def test_startup_compatibility_supports_fedora_core_without_helper(self):
        api, connector = self.make_api()
        del api.validate_connection_availability
        connector.iter_available_protocols.return_value = []
        adapter = ProtonCoreAdapter(api)

        snapshot = await adapter.initialize(Mock())

        self.assertFalse(snapshot.startup_compatible)
        connector.iter_available_protocols.assert_called_once_with("generic")

    async def test_packet_capture_probe_uses_fedora_protocol_group_contract(self):
        api, connector = self.make_api()
        protocol = connector.iter_available_protocols.return_value[0]
        protocol.supports_packet_capture.return_value = True
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        settings = await adapter.get_settings()

        self.assertTrue(settings.packet_capture_supported)
        self.assertTrue(
            all(
                call.args == ("generic",)
                for call in connector.iter_available_protocols.call_args_list
            )
        )

    async def test_support_report_uses_official_api_without_logs(self):
        api, _ = self.make_api()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        await adapter.submit_support_report(
            SupportReport(
                username="test-user",
                email="user@example.com",
                description="A detailed support report that is long enough for submission.",
                include_logs=False,
            )
        )

        api.submit_bug_report.assert_awaited_once()
        form = api.submit_bug_report.await_args.args[0]
        self.assertEqual("test-user", form.username)
        self.assertEqual("KDE Plasma GUI", form.client)
        self.assertEqual([], form.attachments)

    async def test_nps_survey_uses_cached_notification_and_official_api(self):
        api, _ = self.make_api()
        survey = SimpleNamespace(survey_id="survey-1", seen=False, is_active=True)
        api.refresher.notifications.get_nps_survey_notifications.return_value = [survey]
        adapter = ProtonCoreAdapter(api)

        self.assertTrue(await adapter.take_pending_nps_survey())
        api.set_notification_seen.assert_called_once_with("survey-1")

        await adapter.submit_nps_survey(
            NpsSurveyResponse(score=10, comments="Excellent")
        )
        api.submit_nps_response.assert_awaited_once()
        response = api.submit_nps_response.await_args.args[0]
        self.assertEqual(10, response.user_score)
        self.assertEqual("Excellent", response.user_comments)
        self.assertEqual("SUBMIT", response.response_type.name)

    async def test_initialize_reuses_core_and_subscribes_without_connecting(self):
        api, connector = self.make_api()
        adapter = ProtonCoreAdapter(api)

        snapshot = await adapter.initialize(Mock())

        api.get_vpn_connector.assert_awaited_once_with()
        connector.register.assert_any_call(adapter)
        self.assertEqual(2, connector.register.call_count)
        api.refresher.enable.assert_awaited_once_with()
        connector.connect.assert_not_awaited()
        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.logged_in)
        self.assertEqual("disconnected", snapshot.state)
        api.refresher.set_server_list_updated_callback.assert_called_once()
        api.refresher.set_server_loads_updated_callback.assert_called_once()
        api.refresher.set_location_names_updated_callback.assert_called_once()

    async def test_initialize_supports_core_without_location_name_callback(self):
        api, connector = self.make_api()
        del api.refresher.set_location_names_updated_callback
        adapter = ProtonCoreAdapter(api)

        snapshot = await adapter.initialize(Mock())
        self.assertTrue(snapshot.ready)
        api.refresher.set_server_list_updated_callback.assert_called_once()
        api.refresher.set_server_loads_updated_callback.assert_called_once()

        await adapter.close()
        connector.unregister.assert_any_call(adapter)

    async def test_server_refresh_callbacks_preserve_update_scope(self):
        api, _ = self.make_api()
        events = []
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock(), events.append)

        list_callback = api.refresher.set_server_list_updated_callback.call_args.args[0]
        loads_callback = api.refresher.set_server_loads_updated_callback.call_args.args[
            0
        ]
        location_names_callback = (
            api.refresher.set_location_names_updated_callback.call_args.args[0]
        )
        list_callback()
        loads_callback()
        location_names_callback()

        self.assertEqual([True, False, True], events)

    async def test_only_topology_callbacks_discard_the_search_projection(self):
        api, _ = self.make_api()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())
        marker = object()
        adapter._search_projection = marker

        adapter._on_server_loads_updated()
        self.assertIs(marker, adapter._search_projection)
        self.assertEqual(0, adapter._server_list_generation)

        adapter._on_server_list_updated()
        self.assertIsNone(adapter._search_projection)
        self.assertEqual(1, adapter._server_list_generation)

        adapter._search_projection = marker
        adapter._on_location_names_updated()
        self.assertIsNone(adapter._search_projection)
        self.assertEqual(2, adapter._server_list_generation)

    async def test_secret_service_wait_does_not_block_asyncio_thread(self):
        api, connector = self.make_api()
        prompt_started = threading.Event()
        prompt_released = threading.Event()

        def wait_for_provider_approval():
            prompt_started.set()
            prompt_released.wait(timeout=2)
            return True

        api.is_user_logged_in = wait_for_provider_approval
        adapter = ProtonCoreAdapter(api)
        initialize_task = asyncio.create_task(adapter.initialize(Mock()))
        try:
            for _ in range(100):
                if prompt_started.is_set():
                    break
                await asyncio.sleep(0.01)

            self.assertTrue(prompt_started.is_set())
            await asyncio.wait_for(asyncio.sleep(0.01), timeout=0.1)
            self.assertFalse(initialize_task.done())
        finally:
            prompt_released.set()

        await initialize_task
        connector.register.assert_any_call(adapter)

    async def test_logged_out_start_does_not_enable_refresher(self):
        api, _ = self.make_api(logged_in=False)
        adapter = ProtonCoreAdapter(api)

        snapshot = await adapter.initialize(Mock())

        api.refresher.enable.assert_not_awaited()
        self.assertFalse(snapshot.logged_in)
        self.assertEqual("Sign in to Proton VPN to continue", snapshot.message)

    async def test_logged_out_start_exposes_and_disables_permanent_kill_switch(self):
        api, _ = self.make_api(logged_in=False)
        settings = await api.load_settings()
        settings.killswitch = 2
        api.load_settings.reset_mock()
        adapter = ProtonCoreAdapter(api)

        snapshot = await adapter.initialize(Mock())
        self.assertEqual(2, snapshot.kill_switch)

        await adapter.disable_kill_switch_for_login()

        self.assertEqual(0, settings.killswitch)
        api.save_settings.assert_awaited_once_with(settings)

    async def test_login_without_two_factor_enables_session_services(self):
        api, connector = self.make_api(logged_in=False)
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )
        snapshots = []
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(snapshots.append)

        await adapter.login("test-user", "not-recorded")

        api.login.assert_awaited_once_with("test-user", "not-recorded")
        api.refresher.enable.assert_awaited_once_with()
        self.assertTrue(snapshots[-1].logged_in)
        self.assertEqual("signed_in", snapshots[-1].auth_state)
        self.assertEqual("VPN Plus", snapshots[-1].plan_title)
        self.assertEqual(2, connector.register.call_count)

    async def test_two_factor_and_recovery_code_flow(self):
        api, _ = self.make_api(logged_in=False)
        api.login.return_value = SimpleNamespace(
            success=False,
            authenticated=True,
            twofa_required=True,
        )
        api.submit_2fa_code.side_effect = [
            SimpleNamespace(success=False),
            SimpleNamespace(success=True),
        ]
        snapshots = []
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(snapshots.append)

        await adapter.login("test-user", "not-recorded")
        self.assertEqual("two_factor", snapshots[-1].auth_state)
        self.assertFalse(snapshots[-1].logged_in)

        await adapter.submit_two_factor("000000")
        self.assertEqual("two_factor", snapshots[-1].auth_state)
        self.assertIn("Incorrect", snapshots[-1].message)

        await adapter.submit_two_factor("recovery")
        self.assertTrue(snapshots[-1].logged_in)
        self.assertEqual("signed_in", snapshots[-1].auth_state)

    async def test_authentication_exception_does_not_expose_exception_text(self):
        api, _ = self.make_api(logged_in=False)
        api.login.side_effect = RuntimeError("password=super-secret")
        snapshots = []
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(snapshots.append)

        await adapter.login("test-user", "super-secret")

        self.assertNotIn("super-secret", snapshots[-1].message)
        self.assertEqual(
            "Proton could not complete authentication", snapshots[-1].message
        )

    async def test_security_key_flow_uses_official_api(self):
        api, _ = self.make_api(logged_in=False)
        api.supports_fido2 = True
        api.login.return_value = SimpleNamespace(
            success=False,
            authenticated=True,
            twofa_required=True,
        )

        async def generate_assertion(interaction, _cancel_assertion):
            interaction.prompt_up()
            await asyncio.sleep(0)
            return "assertion"

        api.generate_2fa_fido2_assertion.side_effect = generate_assertion
        api.submit_2fa_fido2.return_value = SimpleNamespace(success=True)
        snapshots = []
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(snapshots.append)
        await adapter.login("test-user", "not-recorded")

        await adapter.begin_fido2()

        api.submit_2fa_fido2.assert_awaited_once_with("assertion")
        self.assertTrue(any(item.auth_state == "fido_touch" for item in snapshots))
        self.assertTrue(snapshots[-1].logged_in)

    async def test_logout_disconnects_and_clears_account_metadata(self):
        api, connector = self.make_api()
        connector.current_state = state_named("Connected")
        snapshots = []
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(snapshots.append)

        await adapter.logout()

        connector.disconnect.assert_awaited_once_with()
        api.logout.assert_awaited_once_with()
        self.assertFalse(snapshots[-1].logged_in)
        self.assertEqual("", snapshots[-1].account_name)
        self.assertEqual("signed_out", snapshots[-1].auth_state)

    async def test_failed_logout_restores_persisted_kill_switch(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        unreachable = type("ProtonAPINotReachable", (Exception,), {})
        api.logout.side_effect = unreachable()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "unreachable"):
            await adapter.logout()

        self.assertEqual(2, settings.killswitch)
        self.assertEqual(2, adapter._kill_switch)
        self.assertEqual(2, api.save_settings.await_count)
        self.assertTrue(adapter._logged_in)

    async def test_failed_logout_surfaces_kill_switch_rollback_failure(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 1
        api.logout.side_effect = RuntimeError("remote failure")
        api.save_settings.side_effect = [None, RuntimeError("disk failure")]
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "could not be restored"):
            await adapter.logout()

        self.assertTrue(adapter._logged_in)

    async def test_logout_rolls_back_when_reconnector_disable_fails(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())
        adapter._reconnector.disable = AsyncMock(
            side_effect=RuntimeError("reconnector failure")
        )

        with self.assertRaisesRegex(RuntimeError, "could not complete"):
            await adapter.logout()

        self.assertEqual(2, settings.killswitch)
        self.assertEqual(2, adapter._kill_switch)
        self.assertEqual(2, api.save_settings.await_count)
        api.logout.assert_not_awaited()
        self.assertTrue(adapter._logged_in)

    async def test_expired_api_session_returns_to_sign_in_state(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.refresher.get_up_to_date_server_list.side_effect = expired_error()
        snapshots = []
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await adapter.get_countries()

        self.assertFalse(snapshots[-1].logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)
        api.refresher.disable.assert_awaited_once_with()

    async def test_disabled_reconnection_preference_survives_initialization(self):
        api, connector = self.make_api()
        adapter = ProtonCoreAdapter(api)

        await adapter.set_reconnection_enabled(False)
        snapshot = await adapter.initialize(Mock())

        self.assertFalse(snapshot.reconnect_enabled)
        connector.register.assert_called_once_with(adapter)
        await adapter.close()
        connector.unregister.assert_called_once_with(adapter)

    async def test_state_mapping_exposes_only_safe_connection_metadata(self):
        from proton.vpn.session.servers import ServerFeatureEnum

        api, connector = self.make_api()
        connector.current_connection = SimpleNamespace(server_name="US-IL#42")
        logical_server = SimpleNamespace(
            location="Chicago, IL",
            exit_country="US",
            entry_country="CA",
            features=[ServerFeatureEnum.P2P, ServerFeatureEnum.TOR],
            smart_routing=True,
        )
        api.refresher.server_list = SimpleNamespace(
            get_by_name=Mock(return_value=logical_server)
        )
        adapter = ProtonCoreAdapter(api)
        adapter._connector = connector
        adapter._logged_in = True

        for state_name in (
            "Connected",
            "Connecting",
            "Disconnecting",
            "Disconnected",
            "Error",
        ):
            state = state_named(state_name)
            if state_name == "Connected":
                state.forwarded_port = 43123
            snapshot = adapter._snapshot_from_state(state)
            self.assertEqual(state_name.lower(), snapshot.state)
            self.assertEqual("US-IL#42", snapshot.server_name)

        self.assertEqual("Chicago, IL", snapshot.server_location)
        connected = state_named("Connected")
        connected.forwarded_port = 43123
        snapshot = adapter._snapshot_from_state(connected)
        self.assertEqual(43123, snapshot.forwarded_port)
        self.assertEqual("US", snapshot.exit_country)
        self.assertEqual("CA", snapshot.entry_country)
        self.assertTrue(snapshot.tor)
        self.assertTrue(snapshot.p2p)
        self.assertTrue(snapshot.smart_routing)

        self.assertEqual(
            "error", adapter._snapshot_from_state(state_named("FutureState")).state
        )

        error_codes = {
            "TunnelSetupFailed": "tunnel_setup_failed",
            "AuthDenied": "authentication_denied",
            "Timeout": "timeout",
            "DeviceDisconnected": "device_disconnected",
            "MaximumSessionsReached": "maximum_sessions_reached",
            "ExpiredCertificate": "certificate_expired",
            "NotYetValidCertificate": "certificate_not_yet_valid",
            "TwoFARequired": "two_factor_required",
            "UnexpectedError": "unexpected_error",
            "FutureError": "unexpected_error",
        }
        for event_name, expected_code in error_codes.items():
            with self.subTest(event_name=event_name):
                error_state = state_named("Error")
                error_state.context = SimpleNamespace(event=state_named(event_name))
                self.assertEqual(
                    expected_code,
                    adapter._snapshot_from_state(error_state).error_code,
                )

    async def test_connect_fastest_uses_official_selection_and_saved_protocol(self):
        api, connector = self.make_api()
        logical_server = object()
        server_list = SimpleNamespace(get_fastest=Mock(return_value=logical_server))
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = ProtonCoreAdapter(api)
        adapter._connector = connector

        await adapter.connect_fastest()

        server_list.get_fastest.assert_called_once_with()
        connector.get_vpn_server.assert_called_once_with(
            logical_server, "client-config"
        )
        connector.connect.assert_awaited_once_with("vpn-server", protocol="wireguard")

    async def test_capability_intersection_uses_official_filter_and_score(self):
        from proton.vpn.session.servers import ServerFeatureEnum

        api, connector = self.make_api()
        logical_server = object()
        server_list = SimpleNamespace(
            logicals=[logical_server],
            user_tier=2,
            get_available_servers=Mock(return_value=iter([logical_server])),
            get_servers_with_features=Mock(return_value=iter([logical_server])),
            get_fastest_server=Mock(return_value=logical_server),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = ProtonCoreAdapter(api)
        adapter._connector = connector

        await adapter.connect_fastest_with_features(("p2p", "streaming"))

        server_list.get_available_servers.assert_called_once_with(
            server_list.logicals, server_list.user_tier
        )
        server_list.get_servers_with_features.assert_called_once()
        _, filter_kwargs = server_list.get_servers_with_features.call_args
        self.assertEqual(
            ServerFeatureEnum.P2P | ServerFeatureEnum.STREAMING,
            filter_kwargs["request_features"],
        )
        self.assertEqual(
            ServerFeatureEnum(0),
            filter_kwargs["exclude_features"],
        )
        server_list.get_fastest_server.assert_called_once()
        connector.get_vpn_server.assert_called_once_with(
            logical_server, "client-config"
        )
        connector.connect.assert_awaited_once_with("vpn-server", protocol="wireguard")

    async def test_capability_connect_rejects_unknown_or_unavailable_selection(self):
        api, connector = self.make_api()
        adapter = ProtonCoreAdapter(api)
        adapter._connector = connector

        with self.assertRaisesRegex(ValueError, "supported Proton server capabilities"):
            await adapter.connect_fastest_with_features(("random",))

        server_list = SimpleNamespace(
            logicals=[],
            user_tier=2,
            get_available_servers=Mock(return_value=iter(())),
            get_servers_with_features=Mock(return_value=iter(())),
            get_fastest_server=Mock(return_value=None),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        with self.assertRaisesRegex(RuntimeError, "current tier"):
            await adapter.connect_fastest_with_features(("tor", "p2p"))

        connector.connect.assert_not_awaited()

    async def test_scoped_capability_connect_uses_only_the_selected_pool(self):
        api, connector = self.make_api()
        country_server = object()
        group_server = object()
        group = SimpleNamespace(name="Zurich", servers=[group_server])
        country = SimpleNamespace(
            code="CH",
            servers=[country_server, group_server],
            locations=[group],
            secure_core_group=None,
        )
        server_list = SimpleNamespace(
            logicals=[country_server, group_server],
            user_tier=2,
            group_by_country=Mock(return_value=[country]),
            get_available_servers=Mock(side_effect=lambda items, _: iter(items)),
            get_servers_with_features=Mock(side_effect=lambda items, **_: iter(items)),
            get_fastest_server=Mock(side_effect=[country_server, group_server]),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = ProtonCoreAdapter(api)
        adapter._connector = connector

        await adapter.connect_country_with_features("CH", ("p2p",))
        self.assertIs(
            server_list.get_available_servers.call_args_list[0].args[0],
            country.servers,
        )

        await adapter.connect_group_with_features(
            "CH", "location", "Zurich", ("streaming",)
        )
        self.assertIs(
            server_list.get_available_servers.call_args_list[1].args[0],
            group.servers,
        )
        self.assertEqual(2, connector.connect.await_count)

    async def test_settings_round_trip_uses_official_core_objects(self):
        api, connector = self.make_api()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        current = await adapter.get_settings()
        self.assertEqual("wireguard", current.protocol)
        self.assertEqual("WireGuard", current.protocols[0].name)
        self.assertEqual(1, current.net_shield)
        self.assertTrue(current.protocol_editable)

        updated = await adapter.update_settings(
            {"netShield": 2, "vpnAccelerator": False, "ipv6": False}
        )

        api.save_settings.assert_awaited_once()
        saved = api.save_settings.await_args.args[0]
        self.assertEqual(2, saved.features.netshield)
        self.assertFalse(saved.features.vpn_accelerator)
        self.assertFalse(saved.ipv6)
        self.assertEqual(2, updated.net_shield)
        connector.connect.assert_not_awaited()

    async def test_unofficial_build_persists_crash_reporting_off(self):
        api, _ = self.make_api()
        persisted = api.load_settings.return_value
        persisted.anonymous_crash_reports = True
        api.usage_reporting.enabled = True
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        current = await adapter.get_settings()
        again = await adapter.get_settings()

        self.assertFalse(current.anonymous_crash_reports)
        self.assertFalse(again.anonymous_crash_reports)
        self.assertFalse(persisted.anonymous_crash_reports)
        self.assertFalse(api.usage_reporting.enabled)
        api.save_settings.assert_awaited_once_with(persisted)

    async def test_unofficial_build_rejects_crash_reporting_enable(self):
        api, _ = self.make_api()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "unofficial community build"):
            await adapter.update_settings({"anonymousCrashReports": True})

        api.load_settings.assert_not_awaited()
        api.save_settings.assert_not_awaited()

    async def test_unofficial_build_disables_sender_when_persistence_fails(self):
        api, _ = self.make_api()
        api.load_settings.return_value.anonymous_crash_reports = True
        api.usage_reporting.enabled = True
        api.save_settings.side_effect = RuntimeError("disk failure")
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "save the VPN settings"):
            await adapter.get_settings()

        self.assertFalse(api.usage_reporting.enabled)

    async def test_approved_build_preserves_crash_reporting_preference(self):
        api, _ = self.make_api()
        api.load_settings.return_value.anonymous_crash_reports = True
        api.usage_reporting.enabled = True
        adapter = ProtonCoreAdapter(api, crash_report_submission_enabled=True)
        await adapter.initialize(Mock())

        current = await adapter.get_settings()

        self.assertTrue(current.anonymous_crash_reports)
        self.assertTrue(api.usage_reporting.enabled)
        api.save_settings.assert_not_awaited()

    async def test_connection_sensitive_settings_require_disconnect(self):
        api, connector = self.make_api()
        connector.current_state = state_named("Connected")
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "Disconnect"):
            await adapter.update_settings({"protocol": "wireguard"})
        with self.assertRaisesRegex(RuntimeError, "Disconnect"):
            await adapter.update_settings({"killSwitch": 1})

        api.save_settings.assert_not_awaited()

    async def test_packet_capture_uses_connected_protocol_and_selected_folder(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = ProtonCoreAdapter(api)
        snapshots = []
        await adapter.initialize(snapshots.append)

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            self.assertEqual(
                capture_directory,
                connection.settings.packet_capture.directory_path,
            )
        connection.start_packet_capture.assert_awaited_once_with()
        self.assertTrue(snapshots[-1].packet_capture_active)

        await adapter.stop_packet_capture()
        connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(snapshots[-1].packet_capture_active)

    async def test_packet_capture_fails_closed_without_core_byte_limit(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(directory_path="/tmp")
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            with self.assertRaisesRegex(RuntimeError, "byte limit"):
                await adapter.start_packet_capture(capture_directory)

        connection.start_packet_capture.assert_not_awaited()

    async def test_packet_capture_cannot_replace_an_active_generation(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            with self.assertRaisesRegex(RuntimeError, "already active"):
                await adapter.start_packet_capture(capture_directory)

        connection.start_packet_capture.assert_awaited_once_with()
        await adapter.stop_packet_capture()

    async def test_packet_capture_watchdog_stops_once_and_clears_state(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        snapshots = []
        adapter = ProtonCoreAdapter(api, packet_capture_max_seconds=0.01)
        await adapter.initialize(snapshots.append)

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            await asyncio.sleep(0.05)

        connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(snapshots[-1].packet_capture_active)
        self.assertIn("safety limit", snapshots[-1].message)

    async def test_manual_packet_capture_stop_cancels_watchdog(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = ProtonCoreAdapter(api, packet_capture_max_seconds=0.02)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            await adapter.stop_packet_capture()
            await asyncio.sleep(0.05)

        connection.stop_packet_capture.assert_awaited_once_with()

    async def test_manual_stop_racing_watchdog_calls_core_once(self):
        api, connector = self.make_api()
        stop_entered = asyncio.Event()
        release_stop = asyncio.Event()

        async def stop_capture():
            stop_entered.set()
            await release_stop.wait()

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(side_effect=stop_capture),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = ProtonCoreAdapter(api, packet_capture_max_seconds=0.01)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            await asyncio.wait_for(stop_entered.wait(), timeout=1.0)
            manual_stop = asyncio.create_task(adapter.stop_packet_capture())
            await asyncio.sleep(0)
            release_stop.set()
            await asyncio.wait_for(manual_stop, timeout=1.0)

        connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(adapter._packet_capture_active)

    async def test_settings_conflicts_are_rejected_without_side_effects(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.features.split_tunneling.enabled = True
        settings.custom_dns.enabled = True
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(ValueError, "split tunneling"):
            await adapter.update_settings({"killSwitch": 1})
        with self.assertRaisesRegex(ValueError, "custom DNS"):
            await adapter.update_settings({"netShield": 2})

        api.save_settings.assert_not_awaited()

    async def test_settings_core_failures_are_sanitized(self):
        api, _ = self.make_api()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        api.load_settings.side_effect = RuntimeError("token=must-not-escape")
        with self.assertRaisesRegex(
            RuntimeError, "Proton could not load the VPN settings"
        ) as load_error:
            await adapter.get_settings()
        self.assertNotIn("must-not-escape", str(load_error.exception))

        api.load_settings.side_effect = None
        api.save_settings.side_effect = RuntimeError("secret=must-not-escape")
        with self.assertRaisesRegex(
            RuntimeError, "Proton could not save the VPN settings"
        ) as save_error:
            await adapter.update_settings({"ipv6": False})
        self.assertNotIn("must-not-escape", str(save_error.exception))

    async def test_split_tunneling_round_trip_preserves_ip_ranges(self):
        api, _ = self.make_api()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        current = await adapter.get_split_tunneling()
        self.assertTrue(current.available)
        self.assertEqual(("/usr/bin/firefox",), current.exclude_app_paths)
        self.assertEqual(("10.0.0.0/8",), current.exclude_ip_ranges)

        updated = await adapter.update_split_tunneling(
            {
                "excludeAppPaths": ["/usr/bin/firefox", "/usr/bin/thunderbird"],
                "excludeIpRanges": ["192.168.0.0/16", "2001:db8::/32"],
                "enabled": True,
            }
        )

        saved = api.save_settings.await_args.args[0]
        self.assertTrue(saved.features.split_tunneling.enabled)
        self.assertEqual(
            ["/usr/bin/firefox", "/usr/bin/thunderbird"],
            saved.features.split_tunneling.exclude.app_paths,
        )
        self.assertEqual(
            ["192.168.0.0/16", "2001:db8::/32"],
            saved.features.split_tunneling.exclude.ip_ranges,
        )
        self.assertEqual(
            ("192.168.0.0/16", "2001:db8::/32"),
            updated.exclude_ip_ranges,
        )
        self.assertTrue(updated.enabled)

    async def test_custom_dns_round_trip_uses_official_entries(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.features.netshield = 0
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        current = await adapter.get_custom_dns()
        self.assertFalse(current.enabled)
        self.assertEqual("9.9.9.9", current.servers[0].address)
        self.assertFalse(current.servers[0].enabled)

        updated = await adapter.update_custom_dns(
            {
                "servers": [
                    {"address": "1.1.1.1", "enabled": True},
                    {"address": "2606:4700:4700::1111", "enabled": False},
                ],
                "enabled": True,
            }
        )

        saved = api.save_settings.await_args.args[0]
        self.assertTrue(saved.custom_dns.enabled)
        self.assertEqual("1.1.1.1", saved.custom_dns.ip_list[0].ip.compressed)
        self.assertTrue(saved.custom_dns.ip_list[0].enabled)
        self.assertFalse(saved.custom_dns.ip_list[1].enabled)
        self.assertTrue(updated.enabled)
        self.assertEqual(2, len(updated.servers))

    async def test_custom_dns_conflict_is_rejected_without_side_effects(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(ValueError, "Disable NetShield"):
            await adapter.update_custom_dns({"enabled": True})

        self.assertFalse(settings.custom_dns.enabled)
        self.assertEqual(1, settings.features.netshield)
        api.save_settings.assert_not_awaited()

    async def test_custom_dns_requires_paid_plan(self):
        api, _ = self.make_api()
        api.account_data.max_tier = 0
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "paid Proton VPN plan"):
            await adapter.update_custom_dns({"servers": []})

        api.save_settings.assert_not_awaited()

    async def test_split_tunneling_conflicts_do_not_mutate_other_settings(self):
        api, connector = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 1
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(ValueError, "kill switch"):
            await adapter.update_split_tunneling({"enabled": True})
        self.assertEqual(1, settings.killswitch)
        api.save_settings.assert_not_awaited()

        settings.killswitch = 0
        connector.is_split_tunneling_available = False
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            await adapter.update_split_tunneling({"enabled": True})
        api.save_settings.assert_not_awaited()

    async def test_include_mode_requires_a_target_before_enabling(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(ValueError, "at least one included"):
            await adapter.update_split_tunneling({"mode": "include", "enabled": True})
        self.assertEqual("exclude", settings.features.split_tunneling.mode.value)
        self.assertFalse(settings.features.split_tunneling.enabled)
        api.save_settings.assert_not_awaited()

    async def test_location_queries_include_feature_aware_groups(self):
        from proton.vpn.session.servers import ServerFeatureEnum

        api, _ = self.make_api()

        def server(name, exit_country, location, load, features, entry_country=None):
            return SimpleNamespace(
                name=name,
                exit_country=exit_country,
                exit_country_name=exit_country,
                entry_country=entry_country or exit_country,
                location=location,
                load=load,
                features=features,
                enabled=True,
                under_maintenance=False,
                smart_routing=entry_country not in {None, exit_country},
            )

        normal = server("CH#10", "CH", "Zurich", 42, [ServerFeatureEnum.P2P])
        tor = server("CH-TOR#1", "CH", "Zurich", 27, [ServerFeatureEnum.TOR])
        secure_core = server(
            "CH-DE#1",
            "CH",
            "Zurich",
            35,
            [ServerFeatureEnum.SECURE_CORE],
            "DE",
        )
        us = server(
            "US-NY#5",
            "US",
            "New York, NY",
            18,
            [ServerFeatureEnum.STREAMING],
        )
        zurich_group = SimpleNamespace(
            name="Zurich",
            servers=[normal, tor],
            features={ServerFeatureEnum.P2P, ServerFeatureEnum.TOR},
            under_maintenance=False,
            smart_routing=False,
        )
        secure_core_group = SimpleNamespace(
            name="Via Secure Core",
            servers=[secure_core],
            features={ServerFeatureEnum.SECURE_CORE},
            under_maintenance=False,
            smart_routing=True,
        )
        countries = [
            SimpleNamespace(
                code="ch",
                servers=[normal, tor, secure_core],
                locations=[zurich_group],
                secure_core_group=secure_core_group,
            ),
            SimpleNamespace(
                code="us",
                servers=[us],
                locations=[],
                secure_core_group=None,
            ),
        ]
        servers = [normal, tor, secure_core, us]
        server_list = SimpleNamespace(
            logicals=servers,
            user_tier=2,
            group_by_country=Mock(return_value=countries),
            get_available_servers=Mock(side_effect=lambda items, *_: iter(items)),
            get_by_name=Mock(
                side_effect={server.name: server for server in servers}.__getitem__
            ),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = ProtonCoreAdapter(api)

        countries = await adapter.get_countries()
        groups = await adapter.get_server_groups("CH")
        secure_core_servers = await adapter.get_group_servers(
            "CH", "secure-core", "Via Secure Core"
        )
        location_servers = await adapter.get_group_servers("CH", "location", "Zurich")
        swiss_loads = await adapter.get_server_loads("CH")
        location_search = await adapter.search_locations("zur")
        server_search = await adapter.search_locations("ch#")

        self.assertEqual(["CH", "US"], [country.code for country in countries])
        self.assertEqual(["location", "secure-core"], [group.kind for group in groups])
        self.assertTrue(groups[0].tor)
        self.assertTrue(groups[1].secure_core)
        self.assertEqual("CH-DE#1", secure_core_servers[0].name)
        self.assertEqual("DE", secure_core_servers[0].entry_country)
        self.assertTrue(secure_core_servers[0].smart_routing)
        normal_info = next(item for item in location_servers if item.name == "CH#10")
        self.assertTrue(normal_info.p2p)
        self.assertFalse(normal_info.streaming)
        self.assertEqual(
            {"CH#10", "CH-TOR#1", "CH-DE#1"},
            {load.name for load in swiss_loads},
        )
        self.assertEqual(["Zurich"], [item.name for item in location_search])
        self.assertEqual(["CH#10"], [item.name for item in server_search])

    async def test_free_tier_location_queries_keep_paid_servers_visible(self):
        api, _ = self.make_api()
        api.account_data.max_tier = 0

        def server(name, country, load):
            return SimpleNamespace(
                name=name,
                exit_country=country,
                entry_country=country,
                location="",
                load=load,
                features=[],
                enabled=True,
                under_maintenance=False,
                smart_routing=False,
            )

        free_server = server("CH-FREE#1", "CH", 65)
        paid_server = server("US#1", "US", 5)
        paid_group = SimpleNamespace(name="New York", servers=[paid_server])
        countries = [
            SimpleNamespace(
                code="ch",
                servers=[free_server],
                locations=[],
                secure_core_group=None,
                free=True,
                under_maintenance=False,
            ),
            SimpleNamespace(
                code="us",
                servers=[paid_server],
                locations=[paid_group],
                secure_core_group=None,
                free=False,
                under_maintenance=False,
            ),
        ]
        server_list = SimpleNamespace(
            logicals=[paid_server, free_server],
            user_tier=0,
            group_by_country=Mock(return_value=countries),
            get_available_servers=Mock(
                side_effect=lambda items, *_: (
                    item for item in items if item is free_server
                )
            ),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = ProtonCoreAdapter(api)

        country_info = await adapter.get_countries()
        server_info = await adapter.get_group_servers("US", "location", "New York")

        self.assertTrue(country_info[0].accessible)
        self.assertTrue(country_info[0].free)
        self.assertFalse(country_info[1].accessible)
        self.assertFalse(country_info[1].free)
        self.assertEqual(["US#1"], [item.name for item in server_info])
        self.assertFalse(server_info[0].accessible)

    async def test_targeted_connect_uses_official_server_lookup(self):
        api, connector = self.make_api()
        logical_server = object()
        group = SimpleNamespace(name="Zurich", servers=[logical_server])
        country = SimpleNamespace(code="ch", locations=[group], secure_core_group=None)
        server_list = SimpleNamespace(
            get_fastest_in_country=Mock(return_value=logical_server),
            get_by_name=Mock(return_value=logical_server),
            group_by_country=Mock(return_value=[country]),
            get_available_servers=Mock(return_value=[logical_server]),
            get_fastest_server=Mock(return_value=logical_server),
            user_tier=2,
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = ProtonCoreAdapter(api)
        adapter._connector = connector

        await adapter.connect_country("CH")
        server_list.get_fastest_in_country.assert_called_once_with("CH")
        connector.connect.assert_awaited_once()

        connector.connect.reset_mock()
        await adapter.connect_server("CH#10")
        server_list.get_by_name.assert_called_once_with("CH#10")
        connector.connect.assert_awaited_once()

        connector.connect.reset_mock()
        await adapter.connect_group("CH", "location", "Zurich")
        server_list.get_fastest_server.assert_called_once()
        connector.connect.assert_awaited_once()

    async def test_close_unsubscribes_and_stops_refresher(self):
        api, connector = self.make_api()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        await adapter.close()

        connector.unregister.assert_any_call(adapter)
        self.assertEqual(2, connector.unregister.call_count)
        api.refresher.disable.assert_awaited_once_with()
        api.refresher.set_server_list_updated_callback.assert_called_with(None)
        api.refresher.set_server_loads_updated_callback.assert_called_with(None)
        api.refresher.set_location_names_updated_callback.assert_called_with(None)


if __name__ == "__main__":
    unittest.main()
