from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from proton_vpn_kde_backend.adapters import ProtonCoreAdapter


def state_named(name: str):
    return type(name, (), {})()


class ProtonCoreAdapterTests(unittest.IsolatedAsyncioTestCase):
    def make_api(self, *, logged_in: bool = True):
        connector = SimpleNamespace(
            current_state=state_named("Disconnected"),
            current_connection=None,
            register=Mock(),
            unregister=Mock(),
            get_vpn_server=Mock(return_value="vpn-server"),
            connect=AsyncMock(),
            disconnect=AsyncMock(),
        )
        refresher = SimpleNamespace(
            enable=AsyncMock(),
            disable=AsyncMock(),
            get_up_to_date_server_list=AsyncMock(),
            get_up_to_date_client_config=AsyncMock(return_value="client-config"),
        )
        api = SimpleNamespace(
            get_vpn_connector=AsyncMock(return_value=connector),
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
            load_settings=AsyncMock(return_value=SimpleNamespace(protocol="wireguard")),
        )
        return api, connector

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
        api, connector = self.make_api()
        connector.current_connection = SimpleNamespace(server_name="US-IL#42")
        adapter = ProtonCoreAdapter(api)
        adapter._connector = connector

        for state_name in (
            "Connected",
            "Connecting",
            "Disconnecting",
            "Disconnected",
            "Error",
        ):
            snapshot = adapter._snapshot_from_state(state_named(state_name))
            self.assertEqual(state_name.lower(), snapshot.state)
            self.assertEqual("US-IL#42", snapshot.server_name)

        self.assertEqual(
            "error", adapter._snapshot_from_state(state_named("FutureState")).state
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

    async def test_location_queries_filter_and_serialize_normal_servers(self):
        from proton.vpn.session.servers import ServerFeatureEnum

        api, _ = self.make_api()
        servers = [
            SimpleNamespace(
                name="CH#10",
                exit_country="CH",
                location="Zurich",
                load=42,
                features=[ServerFeatureEnum.P2P],
            ),
            SimpleNamespace(
                name="US-NY#5",
                exit_country="US",
                location="New York, NY",
                load=18,
                features=[ServerFeatureEnum.STREAMING],
            ),
        ]
        server_list = SimpleNamespace(
            logicals=servers,
            user_tier=2,
            get_available_servers=Mock(side_effect=lambda *_: iter(servers)),
            get_servers_with_features=Mock(side_effect=lambda items, **_: items),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = ProtonCoreAdapter(api)

        countries = await adapter.get_countries()
        swiss_servers = await adapter.get_servers("CH")

        self.assertEqual(["CH", "US"], [country.code for country in countries])
        self.assertEqual("CH#10", swiss_servers[0].name)
        self.assertTrue(swiss_servers[0].p2p)
        self.assertFalse(swiss_servers[0].streaming)

    async def test_targeted_connect_uses_official_server_lookup(self):
        api, connector = self.make_api()
        logical_server = object()
        server_list = SimpleNamespace(
            get_fastest_in_country=Mock(return_value=logical_server),
            get_by_name=Mock(return_value=logical_server),
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

    async def test_close_unsubscribes_and_stops_refresher(self):
        api, connector = self.make_api()
        adapter = ProtonCoreAdapter(api)
        await adapter.initialize(Mock())

        await adapter.close()

        connector.unregister.assert_any_call(adapter)
        self.assertEqual(2, connector.unregister.call_count)
        api.refresher.disable.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
