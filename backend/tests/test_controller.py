from __future__ import annotations

import asyncio
import unittest

from proton_vpn_kde_backend.adapters import DemoCoreAdapter
from proton_vpn_kde_backend.controller import (
    BackendController,
    NpsSurveyResponse,
    VpnSnapshot,
    custom_dns_patch_from_json,
    settings_patch_from_json,
    split_tunneling_patch_from_json,
    validate_support_report,
)


class FailingDemoAdapter(DemoCoreAdapter):
    async def connect_fastest(self) -> None:
        raise RuntimeError("credential=must-not-reach-snapshot")


class FailingInitializationAdapter(DemoCoreAdapter):
    async def initialize(self, callback, server_data_callback=None):
        raise RuntimeError("credential=must-not-reach-log")


class BackendControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.controller = BackendController(DemoCoreAdapter())
        self.snapshots: list[VpnSnapshot] = []
        self.controller.subscribe(self.snapshots.append)
        await self.controller.start()

    async def test_start_publishes_ready_disconnected_snapshot(self):
        snapshot = self.controller.snapshot

        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.logged_in)
        self.assertEqual("disconnected", snapshot.state)
        self.assertEqual(1, snapshot.schema_version)

    async def test_startup_failure_logs_only_exception_class(self):
        controller = BackendController(FailingInitializationAdapter())

        with self.assertLogs(
            "proton_vpn_kde_backend.controller", level="ERROR"
        ) as captured:
            await controller.start()

        self.assertEqual("error", controller.snapshot.state)
        self.assertEqual(
            "Backend initialization failed", controller.snapshot.message
        )
        output = "\n".join(captured.output)
        self.assertIn("RuntimeError", output)
        self.assertNotIn("credential=", output)

    async def test_connect_and_disconnect_publish_state_transitions(self):
        await self.controller.connect_fastest()
        self.assertEqual("connected", self.controller.snapshot.state)
        self.assertEqual("US-IL#600", self.controller.snapshot.server_name)

        await self.controller.disconnect()
        self.assertEqual("disconnected", self.controller.snapshot.state)
        self.assertEqual("", self.controller.snapshot.server_name)

        states = [snapshot.state for snapshot in self.snapshots]
        self.assertIn("connecting", states)
        self.assertIn("disconnecting", states)

    async def test_connecting_tunnel_can_be_cancelled_concurrently(self):
        connection = asyncio.create_task(self.controller.connect_fastest())
        for _ in range(20):
            if self.controller.snapshot.state == "connecting":
                break
            await asyncio.sleep(0)

        self.assertEqual("connecting", self.controller.snapshot.state)
        self.assertTrue(self.controller.snapshot.busy)

        await self.controller.disconnect()
        await connection

        self.assertEqual("disconnected", self.controller.snapshot.state)
        self.assertFalse(self.controller.snapshot.busy)
        states = [snapshot.state for snapshot in self.snapshots]
        disconnecting_index = states.index("disconnecting")
        self.assertNotIn("connected", states[disconnecting_index + 1 :])

    async def test_snapshot_json_uses_stable_external_field_names(self):
        payload = self.controller.snapshot.to_json()

        self.assertIn('"schemaVersion":1', payload)
        self.assertIn('"startupCompatible":true', payload)
        self.assertIn('"loggedIn":true', payload)
        self.assertIn('"serverName":""', payload)
        self.assertIn('"forwardedPort":0', payload)
        self.assertIn('"packetCaptureActive":false', payload)
        self.assertIn('"killSwitch":0', payload)
        self.assertIn('"errorCode":""', payload)

    async def test_packet_capture_lifecycle_is_reflected_in_snapshot(self):
        await self.controller.update_settings_json('{"protocol":"protun-udp"}')
        await self.controller.connect_fastest()

        await self.controller.start_packet_capture("/tmp")
        self.assertTrue(self.controller.snapshot.packet_capture_active)

        await self.controller.stop_packet_capture()
        self.assertFalse(self.controller.snapshot.packet_capture_active)

    async def test_support_report_is_validated_and_submitted(self):
        description = "A sufficiently detailed description of the VPN issue I found."

        await self.controller.submit_support_report(
            " demo-user ",
            " user@example.com ",
            f" {description} ",
            "false",
        )

        self.assertEqual("demo-user", self.controller._adapter.last_support_report.username)
        self.assertFalse(self.controller._adapter.last_support_report.include_logs)
        self.assertEqual("Your issue has been reported", self.controller.snapshot.message)

    async def test_pending_nps_survey_is_taken_and_submitted_once(self):
        adapter = DemoCoreAdapter(nps_survey_available=True)
        controller = BackendController(adapter)
        await controller.start()

        self.assertIn(
            '"available":true', await controller.get_pending_nps_survey_json()
        )
        self.assertIn(
            '"available":false', await controller.get_pending_nps_survey_json()
        )
        await controller.submit_nps_survey("9", "Works well on Plasma", "submit")

        self.assertEqual(
            NpsSurveyResponse(score=9, comments="Works well on Plasma"),
            adapter.last_nps_response,
        )
        with self.assertRaisesRegex(ValueError, "0 through 10"):
            await controller.submit_nps_survey("11", "", "submit")

    def test_support_report_rejects_invalid_or_oversized_fields(self):
        with self.assertRaisesRegex(ValueError, "valid email"):
            validate_support_report("user", "invalid", "x" * 50, "true")
        with self.assertRaisesRegex(ValueError, "at least 50"):
            validate_support_report("user", "user@example.com", "too short", "true")
        with self.assertRaisesRegex(ValueError, "log choice"):
            validate_support_report("user", "user@example.com", "x" * 50, "yes")

    async def test_location_payloads_are_versioned_and_validated(self):
        countries = await self.controller.get_countries_json()
        groups = await self.controller.get_server_groups_json(" ch ")
        group_servers = await self.controller.get_group_servers_json(
            " ch ", "secure-core", "Via Secure Core"
        )
        servers = await self.controller.get_servers_json(" ch ")
        loads = await self.controller.get_server_loads_json(" ch ")
        location_search = await self.controller.search_locations_json(" zur ")
        server_search = await self.controller.search_locations_json(" CH# ")

        self.assertIn('"schemaVersion":1', countries)
        self.assertIn('"code":"CH"', countries)
        self.assertIn('"serverCount":3', countries)
        self.assertIn('"kind":"secure-core"', groups)
        self.assertIn('"secureCore":true', groups)
        self.assertIn('"entryCountry":"DE"', group_servers)
        self.assertIn('"name":"CH#101"', servers)
        self.assertIn('"loads"', loads)
        self.assertIn('"load":24', loads)
        self.assertIn('"kind":"location"', location_search)
        self.assertIn('"name":"Zurich"', location_search)
        self.assertIn('"kind":"server"', server_search)
        self.assertIn('"name":"CH#101"', server_search)

        with self.assertRaisesRegex(ValueError, "Invalid country code"):
            await self.controller.get_servers_json("Switzerland")
        with self.assertRaisesRegex(ValueError, "Invalid Proton server group"):
            await self.controller.get_group_servers_json("CH", "onion", "Zurich")
        with self.assertRaisesRegex(ValueError, "valid location search"):
            await self.controller.search_locations_json("   ")

    async def test_targeted_connect_methods_use_normalized_identifiers(self):
        await self.controller.connect_country(" us ")
        self.assertEqual("US#FASTEST", self.controller.snapshot.server_name)

        await self.controller.connect_server(" US-NY#88 ")
        self.assertEqual("US-NY#88", self.controller.snapshot.server_name)

        await self.controller.connect_group("CH", "location", "Zurich")
        self.assertEqual("CH#101", self.controller.snapshot.server_name)

    async def test_connected_snapshot_exposes_assigned_forwarded_port(self):
        await self.controller.update_settings_json('{"portForwarding":true}')
        await self.controller.connect_server("CH-DE#1")

        snapshot = self.controller.snapshot
        self.assertEqual(51820, snapshot.forwarded_port)
        self.assertEqual("CH", snapshot.exit_country)
        self.assertEqual("DE", snapshot.entry_country)
        self.assertTrue(snapshot.secure_core)

    async def test_reconnection_preference_is_reflected_in_snapshot(self):
        await self.controller.set_reconnection_enabled(False)

        self.assertFalse(self.controller.snapshot.reconnect_enabled)
        self.assertIn('"reconnectEnabled":false', self.controller.snapshot.to_json())

    async def test_settings_payload_is_versioned_and_updates_atomically(self):
        events = []
        self.controller.subscribe_settings(events.append)

        initial = await self.controller.get_settings_json()
        updated = await self.controller.update_settings_json(
            '{"netShield":2,"vpnAccelerator":false}'
        )

        self.assertIn('"schemaVersion":1', initial)
        self.assertIn('"protocols"', initial)
        self.assertIn('"netShield":2', updated)
        self.assertIn('"vpnAccelerator":false', updated)
        self.assertEqual(2, events[-1].net_shield)
        self.assertFalse(events[-1].vpn_accelerator)

    async def test_settings_patch_rejects_unknown_and_wrong_typed_values(self):
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            settings_patch_from_json('{"password":"must-not-be-accepted"}')
        with self.assertRaisesRegex(ValueError, "wrong value type"):
            settings_patch_from_json('{"killSwitch":true}')
        with self.assertRaisesRegex(ValueError, "valid NetShield"):
            settings_patch_from_json('{"netShield":9}')

    async def test_split_tunneling_payload_updates_and_syncs_scalar_settings(self):
        events = []
        settings_events = []
        self.controller.subscribe_split_tunneling(events.append)
        self.controller.subscribe_settings(settings_events.append)

        initial = await self.controller.get_split_tunneling_json()
        updated = await self.controller.update_split_tunneling_json(
            '{"excludeAppPaths":["/usr/bin/firefox"],'
            '"excludeIpRanges":["192.168.1.23/24"],"enabled":true}'
        )

        self.assertIn('"available":true', initial)
        self.assertIn('"excludeAppPaths":["/usr/bin/firefox"]', updated)
        self.assertIn('"excludeIpRanges":["192.168.1.0/24"]', updated)
        self.assertIn('"enabled":true', updated)
        self.assertEqual(("/usr/bin/firefox",), events[-1].exclude_app_paths)
        self.assertEqual(("192.168.1.0/24",), events[-1].exclude_ip_ranges)
        self.assertTrue(settings_events[-1].split_tunneling_enabled)

    async def test_split_tunneling_patch_rejects_unsafe_application_paths(self):
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            split_tunneling_patch_from_json('{"password":"no"}')
        with self.assertRaisesRegex(ValueError, "wrong type"):
            split_tunneling_patch_from_json('{"enabled":1}')
        with self.assertRaisesRegex(ValueError, "specific application"):
            split_tunneling_patch_from_json('{"excludeAppPaths":["/"]}')
        with self.assertRaisesRegex(ValueError, "cannot bypass"):
            split_tunneling_patch_from_json(
                '{"excludeAppPaths":["/usr/bin/proton-vpn-kde"]}'
            )
        with self.assertRaisesRegex(ValueError, "selected twice"):
            split_tunneling_patch_from_json(
                '{"excludeAppPaths":["/usr/bin/firefox","/usr/bin/firefox"]}'
            )
        with self.assertRaisesRegex(ValueError, "valid IPv4 or IPv6"):
            split_tunneling_patch_from_json(
                '{"excludeIpRanges":["not-a-network"]}'
            )
        with self.assertRaisesRegex(ValueError, "selected twice"):
            split_tunneling_patch_from_json(
                '{"excludeIpRanges":["10.0.0.1/8","10.0.0.0/8"]}'
            )

    async def test_custom_dns_payload_updates_and_syncs_scalar_settings(self):
        events = []
        settings_events = []
        self.controller.subscribe_custom_dns(events.append)
        self.controller.subscribe_settings(settings_events.append)

        initial = await self.controller.get_custom_dns_json()
        updated = await self.controller.update_custom_dns_json(
            '{"servers":[{"address":"2606:4700:4700:0:0:0:0:1111",'
            '"enabled":true}],"enabled":true}'
        )

        self.assertIn('"paidFeaturesAvailable":true', initial)
        self.assertIn('"address":"2606:4700:4700::1111"', updated)
        self.assertIn('"enabled":true', updated)
        self.assertEqual("2606:4700:4700::1111", events[-1].servers[0].address)
        self.assertTrue(settings_events[-1].custom_dns_enabled)

    async def test_custom_dns_patch_validates_addresses_and_entries(self):
        normalized = custom_dns_patch_from_json(
            '{"servers":[{"address":"2001:db8:0:0::1","enabled":false}]}'
        )
        self.assertEqual("2001:db8::1", normalized["servers"][0]["address"])

        with self.assertRaisesRegex(ValueError, "unsupported field"):
            custom_dns_patch_from_json('{"provider":"example"}')
        with self.assertRaisesRegex(ValueError, "wrong type"):
            custom_dns_patch_from_json('{"enabled":1}')
        with self.assertRaisesRegex(ValueError, "valid IPv4 or IPv6"):
            custom_dns_patch_from_json(
                '{"servers":[{"address":"dns.example","enabled":true}]}'
            )
        preserved = custom_dns_patch_from_json(
            '{"servers":['
            '{"address":"2001:db8::1","enabled":true},'
            '{"address":"2001:0db8:0:0:0:0:0:1","enabled":false}]}'
        )
        self.assertEqual(2, len(preserved["servers"]))
        self.assertEqual(
            preserved["servers"][0]["address"],
            preserved["servers"][1]["address"],
        )
    async def test_demo_authentication_and_logout_lifecycle(self):
        controller = BackendController(DemoCoreAdapter(logged_in=False))
        await controller.start()

        await controller.login("demo-user", "2fa")
        self.assertEqual("two_factor", controller.snapshot.auth_state)
        self.assertFalse(controller.snapshot.logged_in)

        await controller.submit_two_factor("123456")
        self.assertTrue(controller.snapshot.logged_in)
        self.assertEqual("demo-user", controller.snapshot.account_name)

        await controller.logout()
        self.assertFalse(controller.snapshot.logged_in)
        self.assertEqual("signed_out", controller.snapshot.auth_state)

    async def test_permanent_kill_switch_must_be_disabled_before_login(self):
        controller = BackendController(
            DemoCoreAdapter(logged_in=False, kill_switch=2)
        )
        await controller.start()

        self.assertEqual(2, controller.snapshot.kill_switch)
        with self.assertRaisesRegex(RuntimeError, "permanent kill switch"):
            await controller.login("demo-user", "password")

        await controller.disable_kill_switch_for_login()
        self.assertEqual(0, controller.snapshot.kill_switch)
        await controller.login("demo-user", "password")
        self.assertTrue(controller.snapshot.logged_in)

    async def test_logout_disables_kill_switch(self):
        controller = BackendController(DemoCoreAdapter(kill_switch=2))
        await controller.start()

        await controller.logout()

        self.assertFalse(controller.snapshot.logged_in)
        self.assertEqual(0, controller.snapshot.kill_switch)

    async def test_authentication_input_is_validated_before_reaching_adapter(self):
        controller = BackendController(DemoCoreAdapter(logged_in=False))
        await controller.start()

        with self.assertRaisesRegex(ValueError, "valid Proton username"):
            await controller.login("   ", "password")
        with self.assertRaisesRegex(ValueError, "6-digit"):
            await controller.submit_two_factor("123")

    async def test_operation_exception_text_is_not_published(self):
        controller = BackendController(FailingDemoAdapter())
        await controller.start()

        with self.assertRaises(RuntimeError):
            await controller.connect_fastest()

        self.assertEqual(
            "The VPN operation could not be completed",
            controller.snapshot.message,
        )
        self.assertNotIn("must-not-reach-snapshot", controller.snapshot.to_json())


if __name__ == "__main__":
    unittest.main()
