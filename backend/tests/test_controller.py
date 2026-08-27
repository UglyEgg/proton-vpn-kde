from __future__ import annotations

import unittest

from proton_vpn_kde_backend.adapters import DemoCoreAdapter
from proton_vpn_kde_backend.controller import BackendController, VpnSnapshot


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
