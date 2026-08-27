from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from proton_vpn_kde_backend.reconnector import AsyncReconnector


def state_named(state_name: str, event_name: str = "UnexpectedError"):
    event = type(event_name, (), {})()
    state = type(state_name, (), {})()
    state.context = SimpleNamespace(event=event)
    return state


class FakeSessionProbe:
    def __init__(self, unlocked: bool = True):
        self.is_unlocked = AsyncMock(return_value=unlocked)
        self.close = AsyncMock()


class AsyncReconnectorTests(unittest.IsolatedAsyncioTestCase):
    def make_reconnector(
        self,
        *,
        event_name: str = "UnexpectedError",
        network_probe=None,
        session_probe=None,
    ):
        connection = SimpleNamespace(
            server_id="server-id",
            protocol="wireguard",
            backend="networkmanager",
        )
        connector = SimpleNamespace(
            current_state=state_named("Error", event_name),
            current_connection=connection,
            register=Mock(),
            unregister=Mock(),
            get_vpn_server=Mock(return_value="vpn-server"),
            connect=AsyncMock(),
        )
        server_list = SimpleNamespace(get_by_id=Mock(return_value="logical-server"))
        refresher = SimpleNamespace(
            server_list=server_list,
            client_config="client-config",
            force_refresh_certificate=Mock(),
        )
        messages = []
        reconnector = AsyncReconnector(
            connector,
            refresher,
            messages.append,
            network_probe=network_probe or AsyncMock(return_value=True),
            session_probe=session_probe or FakeSessionProbe(),
            delay_factory=lambda _attempt: 0,
        )
        return reconnector, connector, refresher, messages

    async def let_tasks_run(self):
        for _ in range(5):
            await asyncio.sleep(0)

    async def test_reconnects_same_server_after_nonfatal_drop(self):
        reconnector, connector, refresher, messages = self.make_reconnector()

        reconnector.enable()
        await self.let_tasks_run()

        refresher.server_list.get_by_id.assert_called_once_with("server-id")
        connector.get_vpn_server.assert_called_once_with(
            "logical-server", "client-config"
        )
        connector.connect.assert_awaited_once_with(
            "vpn-server", "wireguard", "networkmanager"
        )
        self.assertIn("Reconnecting…", messages)
        await reconnector.disable()

    async def test_authentication_error_is_not_retried(self):
        reconnector, connector, _, messages = self.make_reconnector(
            event_name="AuthDenied"
        )

        reconnector.enable()
        await self.let_tasks_run()

        connector.connect.assert_not_awaited()
        self.assertIn("Automatic reconnection is unavailable for this error", messages)
        await reconnector.disable()

    async def test_expired_certificate_requests_refresh(self):
        reconnector, connector, refresher, _ = self.make_reconnector(
            event_name="ExpiredCertificate"
        )

        reconnector.enable()
        await self.let_tasks_run()

        refresher.force_refresh_certificate.assert_called_once_with()
        connector.connect.assert_not_awaited()
        await reconnector.disable()

    async def test_waits_for_network_before_retrying(self):
        network_probe = AsyncMock(side_effect=[False, True])
        reconnector, connector, _, messages = self.make_reconnector(
            network_probe=network_probe
        )

        reconnector.enable()
        await self.let_tasks_run()

        self.assertGreaterEqual(network_probe.await_count, 2)
        connector.connect.assert_awaited_once()
        self.assertIn("Waiting for network connectivity…", messages)
        await reconnector.disable()


if __name__ == "__main__":
    unittest.main()
