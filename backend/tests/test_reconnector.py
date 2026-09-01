# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from proton_vpn_kde_backend.reconnector import AsyncReconnector, LogindSessionProbe


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
        delay_factory=None,
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
            delay_factory=delay_factory or (lambda _attempt: 0),
        )
        return reconnector, connector, refresher, messages

    async def let_tasks_run(self):
        for _ in range(5):
            await asyncio.sleep(0)

    async def wait_until(self, predicate, message: str):
        for _ in range(20):
            if predicate():
                return
            await asyncio.sleep(0)
        self.fail(message)

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

    async def test_disable_quiesces_retries_when_observer_unregistration_fails(self):
        reconnector, connector, _, _ = self.make_reconnector()
        reconnector.enable()
        connector.unregister.side_effect = RuntimeError("observer failure")

        with self.assertRaisesRegex(RuntimeError, "observer failure"):
            await reconnector.disable()

        self.assertFalse(reconnector.enabled)

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

    async def test_network_probe_failure_remains_retryable(self):
        network_probe = AsyncMock(side_effect=[OSError("route failed"), True])
        reconnector, connector, _, messages = self.make_reconnector(
            network_probe=network_probe
        )

        with self.assertLogs(
            "proton_vpn_kde_backend.reconnector", level="ERROR"
        ) as captured:
            reconnector.enable()
            await self.let_tasks_run()

        self.assertTrue(reconnector.enabled)
        self.assertGreaterEqual(network_probe.await_count, 2)
        connector.connect.assert_awaited_once()
        self.assertIn("Waiting for network connectivity…", messages)
        self.assertIn("OSError", "\n".join(captured.output))
        self.assertNotIn("route failed", "\n".join(captured.output))
        await reconnector.disable()

    async def test_waits_for_previous_connection_then_retries(self):
        reconnector, connector, _, messages = self.make_reconnector(
            delay_factory=lambda _attempt: 0
        )
        previous_connection = connector.current_connection
        connector.current_connection = None

        reconnector.enable()
        await self.wait_until(
            lambda: "Waiting for the previous VPN connection…" in messages,
            "The missing previous connection was not observed",
        )

        connector.connect.assert_not_awaited()

        connector.current_connection = previous_connection
        await self.wait_until(
            lambda: connector.connect.await_count == 1,
            "The previous VPN connection was not retried",
        )

        connector.connect.assert_awaited_once()
        await reconnector.disable()

    async def test_disable_during_network_probe_cancels_pending_reconnect(self):
        probe_started = asyncio.Event()
        release_probe = asyncio.Event()

        async def blocking_network_probe():
            probe_started.set()
            await release_probe.wait()
            return True

        reconnector, connector, _, _ = self.make_reconnector(
            network_probe=blocking_network_probe
        )

        reconnector.enable()
        await probe_started.wait()
        await reconnector.disable()
        release_probe.set()
        await self.let_tasks_run()

        self.assertFalse(reconnector.enabled)
        connector.connect.assert_not_awaited()

    async def test_reconnection_exception_text_is_not_published_or_logged(self):
        reconnector, connector, _, messages = self.make_reconnector()
        sentinel = "credential=must-not-reach-snapshot /workspace/private.py"
        connector.connect.side_effect = [RuntimeError(sentinel), None]

        with self.assertLogs(
            "proton_vpn_kde_backend.reconnector", level="ERROR"
        ) as captured:
            reconnector.enable()
            await self.let_tasks_run()

        self.assertIn("Reconnection failed", messages)
        self.assertFalse(any(sentinel in message for message in messages))
        log_output = "\n".join(captured.output)
        self.assertIn("RuntimeError", log_output)
        self.assertNotIn(sentinel, log_output)
        await reconnector.disable()

    async def test_pathological_retry_count_remains_capped_and_scheduled(self):
        reconnector, _, _, messages = self.make_reconnector(
            delay_factory=AsyncReconnector._retry_delay
        )
        reconnector._retry_counter = 1024

        reconnector.enable()
        await asyncio.sleep(0)

        self.assertTrue(reconnector.enabled)
        self.assertIsNotNone(reconnector._retry_task)
        self.assertFalse(reconnector._retry_task.done())
        self.assertIn("Reconnecting in 60.0 seconds…", messages)
        await reconnector.disable()

    async def test_logind_proxy_disconnects_temporary_bus_when_cancelled(self):
        bus = SimpleNamespace(
            introspect=AsyncMock(side_effect=asyncio.CancelledError()),
            disconnect=Mock(),
        )
        message_bus = Mock(
            return_value=SimpleNamespace(
                connect=AsyncMock(return_value=bus),
            )
        )
        modules = {
            "dbus_fast.aio": SimpleNamespace(MessageBus=message_bus),
            "dbus_fast.constants": SimpleNamespace(
                BusType=SimpleNamespace(SYSTEM="system")
            ),
        }
        probe = LogindSessionProbe()

        with patch.dict(sys.modules, modules):
            with self.assertRaises(asyncio.CancelledError):
                await probe._ensure_proxy()

        bus.disconnect.assert_called_once_with()
        self.assertIsNone(probe._bus)
        self.assertIsNone(probe._properties)


if __name__ == "__main__":
    unittest.main()
