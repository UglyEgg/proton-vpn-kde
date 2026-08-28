from __future__ import annotations

import asyncio
import unittest

from proton_vpn_kde_backend.adapters import DemoCoreAdapter
from proton_vpn_kde_backend.controller import (
    BackendController,
    VpnSnapshot,
    custom_dns_patch_from_json,
    settings_patch_from_json,
    split_tunneling_patch_from_json,
)


class FailingDemoAdapter(DemoCoreAdapter):
    async def connect_fastest(self) -> None:
        raise RuntimeError("credential=must-not-reach-snapshot")


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
        self.assertIn('"loggedIn":true', payload)
        self.assertIn('"serverName":""', payload)

    async def test_location_payloads_are_versioned_and_validated(self):
        countries = await self.controller.get_countries_json()
        servers = await self.controller.get_servers_json(" ch ")
        loads = await self.controller.get_server_loads_json(" ch ")

        self.assertIn('"schemaVersion":1', countries)
        self.assertIn('"code":"CH"', countries)
        self.assertIn('"serverCount":3', countries)
        self.assertIn('"name":"CH#101"', servers)
        self.assertIn('"loads"', loads)
        self.assertIn('"load":24', loads)

        with self.assertRaisesRegex(ValueError, "Invalid country code"):
            await self.controller.get_servers_json("Switzerland")

    async def test_targeted_connect_methods_use_normalized_identifiers(self):
        await self.controller.connect_country(" us ")
        self.assertEqual("US#FASTEST", self.controller.snapshot.server_name)

        await self.controller.connect_server(" US-NY#88 ")
        self.assertEqual("US-NY#88", self.controller.snapshot.server_name)

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
            '{"excludeAppPaths":["/usr/bin/firefox"],"enabled":true}'
        )

        self.assertIn('"available":true', initial)
        self.assertIn('"excludeAppPaths":["/usr/bin/firefox"]', updated)
        self.assertIn('"enabled":true', updated)
        self.assertEqual(("/usr/bin/firefox",), events[-1].exclude_app_paths)
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
