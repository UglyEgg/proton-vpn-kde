# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from proton_vpn_kde_backend.reconnector import (
    AsyncReconnector,
    LogindSessionProbe,
    network_route_available,
)


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
    async def test_logind_probe_reports_current_lock_state(self):
        probe = LogindSessionProbe()
        probe._ensure_proxy = AsyncMock()
        properties = SimpleNamespace(call_get=AsyncMock())
        probe._properties = properties

        for locked, expected_unlocked in ((True, False), (False, True)):
            with self.subTest(locked=locked):
                properties.call_get.return_value = SimpleNamespace(value=locked)
                self.assertEqual(expected_unlocked, await probe.is_unlocked())

        probe._ensure_proxy.assert_awaited()

    async def test_logind_probe_preserves_retry_when_logind_is_unavailable(self):
        probe = LogindSessionProbe()
        probe._ensure_proxy = AsyncMock(side_effect=RuntimeError("unavailable"))

        self.assertTrue(await probe.is_unlocked())

    async def test_logind_close_clears_state_even_when_disconnect_wait_fails(self):
        bus = SimpleNamespace(
            disconnect=Mock(),
            wait_for_disconnect=AsyncMock(side_effect=RuntimeError("closed")),
        )
        probe = LogindSessionProbe()
        probe._bus = bus
        probe._properties = Mock()

        await probe.close()

        bus.disconnect.assert_called_once_with()
        bus.wait_for_disconnect.assert_awaited_once_with()
        self.assertIsNone(probe._bus)
        self.assertIsNone(probe._properties)

    async def test_network_probe_uses_packaged_ip_under_hostile_path(self):
        process = SimpleNamespace(wait=AsyncMock(return_value=0), returncode=0)
        with (
            patch.dict(os.environ, {"PATH": "/tmp/attacker"}),
            patch(
                "proton_vpn_kde_backend.reconnector.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ) as create_process,
        ):
            self.assertTrue(await network_route_available())

        create_process.assert_awaited_once_with(
            "/usr/bin/ip",
            "route",
            "get",
            "192.0.2.1",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def test_network_probe_fails_when_packaged_ip_is_unavailable(self):
        with patch(
            "proton_vpn_kde_backend.reconnector.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=FileNotFoundError),
        ) as create_process:
            self.assertFalse(await network_route_available())

        create_process.assert_awaited_once_with(
            "/usr/bin/ip",
            "route",
            "get",
            "192.0.2.1",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def test_route_probe_timeout_and_cancellation_reap_owned_child(self):
        for cancelled in (False, True):
            for ignore_terminate in (False, True):
                with self.subTest(cancelled=cancelled, ignore_terminate=ignore_terminate):
                    waiting = asyncio.Event()
                    stopped = asyncio.Event()
                    process = SimpleNamespace(returncode=None)

                    async def wait(waiting=waiting, stopped=stopped, process=process):
                        waiting.set()
                        await stopped.wait()
                        return process.returncode

                    def stop(process=process, stopped=stopped):
                        process.returncode = -9
                        stopped.set()

                    process.wait = AsyncMock(side_effect=wait)
                    process.terminate = Mock(side_effect=None if ignore_terminate else stop)
                    process.kill = Mock(side_effect=stop)
                    with (
                        patch("proton_vpn_kde_backend.reconnector.asyncio.create_subprocess_exec",
                              new=AsyncMock(return_value=process)),
                        patch("proton_vpn_kde_backend.reconnector.ROUTE_PROBE_SECONDS", 0.01),
                        patch("proton_vpn_kde_backend.reconnector.ROUTE_PROBE_STOP_SECONDS", 0.01),
                    ):
                        probe = asyncio.create_task(network_route_available())
                        await waiting.wait()
                        if cancelled:
                            probe.cancel()
                            with self.assertRaises(asyncio.CancelledError):
                                await probe
                        else:
                            self.assertFalse(await probe)
                    self.assertIsNotNone(process.returncode)
                    process.terminate.assert_called_once_with()
                    self.assertEqual(int(ignore_terminate), process.kill.call_count)

    async def test_route_probe_cancellation_during_spawn_retains_child_ownership(self):
        spawning = asyncio.Event()
        release_spawn = asyncio.Event()
        process = SimpleNamespace(returncode=None, wait=AsyncMock(return_value=-15))

        def stop():
            process.returncode = -15

        process.terminate = Mock(side_effect=stop)
        process.kill = Mock()

        async def spawn(*_args, **_kwargs):
            spawning.set()
            await release_spawn.wait()
            return process

        with patch("proton_vpn_kde_backend.reconnector.asyncio.create_subprocess_exec", new=spawn):
            probe = asyncio.create_task(network_route_available())
            await spawning.wait()
            probe.cancel()
            release_spawn.set()
            with self.assertRaises(asyncio.CancelledError):
                await probe
        process.terminate.assert_called_once_with()
        process.wait.assert_awaited_once_with()
        process.kill.assert_not_called()

    async def test_network_probe_propagates_non_missing_executable_failures(self):
        with patch(
            "proton_vpn_kde_backend.reconnector.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=PermissionError),
        ):
            with self.assertRaises(PermissionError):
                await network_route_available()

    def make_reconnector(
        self,
        *,
        event_name: str = "UnexpectedError",
        network_probe=None,
        session_probe=None,
        delay_factory=None,
        authentication_epoch_source=None,
        authentication_epoch_validator=None,
        authentication_error_callback=None,
        connection_attempt=None,
    ):
        connection = SimpleNamespace(
            server_id="server-id",
            protocol="wireguard",
            backend="networkmanager",
        )
        attempt = (
            connection_attempt
            if connection_attempt is not None
            else AsyncMock(return_value=True)
        )
        connector = SimpleNamespace(
            current_state=state_named("Error", event_name),
            current_connection=connection,
            register=Mock(),
            unregister=Mock(),
            get_vpn_server=Mock(return_value="vpn-server"),
            connect=AsyncMock(side_effect=AssertionError("Retry policy cannot call Core Up")),
            disconnect=AsyncMock(side_effect=AssertionError("Retry policy cannot call Core Down")),
        )
        self.addCleanup(connector.connect.assert_not_awaited)
        self.addCleanup(connector.disconnect.assert_not_awaited)
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
            authentication_epoch_source=authentication_epoch_source or (lambda: 7),
            authentication_epoch_validator=(
                authentication_epoch_validator or (lambda epoch: epoch == 7)
            ),
            authentication_error_callback=authentication_error_callback or AsyncMock(),
            connection_attempt=attempt,
        )
        return reconnector, connector, refresher, messages, attempt

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
        reconnector, connector, refresher, messages, attempt = self.make_reconnector()

        reconnector.enable()
        await self.let_tasks_run()

        refresher.server_list.get_by_id.assert_called_once_with("server-id")
        connector.get_vpn_server.assert_called_once_with(
            "logical-server", "client-config"
        )
        attempt.assert_awaited_once_with(
            "vpn-server", "wireguard", "networkmanager", 7
        )
        self.assertIn("Reconnecting…", messages)
        await reconnector.disable()

    async def test_adapter_owned_attempt_replaces_direct_connector_call(self):
        attempt = AsyncMock(return_value=True)
        reconnector, connector, _, _, attempt = self.make_reconnector(
            authentication_epoch_source=lambda: 7,
            authentication_epoch_validator=lambda epoch: epoch == 7,
            connection_attempt=attempt,
        )

        reconnector.enable()
        await self.let_tasks_run()

        attempt.assert_awaited_once_with(
            "vpn-server", "wireguard", "networkmanager", 7
        )
        connector.connect.assert_not_awaited()
        await reconnector.disable()

    async def test_shutdown_fence_survives_failed_suspension_and_reenable(self):
        reconnector, connector, _, _, attempt = self.make_reconnector()
        reconnector.enable()
        reconnector.begin_shutdown()
        with self.assertRaisesRegex(RuntimeError, "teardown failed"):
            async with reconnector.suspended(deadline=asyncio.get_running_loop().time() + 1):
                raise RuntimeError("teardown failed")
        reconnector.status_update(connector.current_state)
        reconnector.enable()
        await self.let_tasks_run()
        attempt.assert_not_awaited()
        connector.register.assert_called_once_with(reconnector)
        await reconnector.disable(deadline=asyncio.get_running_loop().time() + 1)
        self.assertFalse(reconnector.enabled)
        self.assertFalse(reconnector._retiring_retry_tasks)

    async def test_owner_callbacks_are_required_before_service_construction(self):
        callbacks = {
            "connection_attempt": AsyncMock(return_value=True),
            "authentication_epoch_source": lambda: 7,
            "authentication_epoch_validator": lambda epoch: epoch == 7,
            "authentication_error_callback": AsyncMock(),
        }
        connector = SimpleNamespace(register=Mock())
        for name in callbacks:
            for missing in (True, False):
                with self.subTest(callback=name, missing=missing):
                    provided = dict(callbacks)
                    if missing:
                        provided.pop(name)
                    else:
                        provided[name] = None
                    with self.assertRaisesRegex(TypeError, name):
                        AsyncReconnector(connector, object(), **provided)
                    connector.register.assert_not_called()

    async def test_owner_rejection_is_terminal_for_that_retry(self):
        attempt = AsyncMock(return_value=False)
        reconnector, _, _, _, _ = self.make_reconnector(connection_attempt=attempt)
        reconnector.enable()
        await self.let_tasks_run()

        attempt.assert_awaited_once_with(
            "vpn-server", "wireguard", "networkmanager", 7
        )
        self.assertIsNone(reconnector._retry_task)
        self.assertFalse(reconnector._retry_pending)
        await reconnector.disable()

    async def test_stale_account_cannot_request_a_connection_attempt(self):
        reconnector, _, _, messages, attempt = self.make_reconnector(
            authentication_epoch_validator=lambda _epoch: False,
        )
        reconnector.enable()
        await self.let_tasks_run()

        attempt.assert_not_awaited()
        self.assertNotIn("Reconnecting…", messages)
        self.assertIsNone(reconnector._retry_task)
        await reconnector.disable()

    async def test_nested_suspend_owners_cannot_resume_each_other(self):
        reconnector, connector, _, _, attempt = self.make_reconnector()
        connector.current_state = state_named("Disconnected")
        reconnector.enable()

        async with reconnector.suspended():
            self.assertTrue(reconnector._suspended)
            self.assertEqual(1, reconnector._suspend_count)
            async with reconnector.suspended():
                self.assertTrue(reconnector._suspended)
                self.assertEqual(2, reconnector._suspend_count)
            self.assertTrue(reconnector._suspended)
            self.assertEqual(1, reconnector._suspend_count)
        self.assertFalse(reconnector._suspended)
        self.assertEqual(0, reconnector._suspend_count)
        await reconnector.disable()

    async def test_suspension_scope_releases_after_body_error_and_cancellation(self):
        reconnector, connector, _, _, attempt = self.make_reconnector()
        connector.current_state = state_named("Disconnected")
        reconnector.enable()

        with self.assertRaisesRegex(RuntimeError, "body failure"):
            async with reconnector.suspended():
                raise RuntimeError("body failure")
        self.assertEqual(0, reconnector._suspend_count)

        entered = asyncio.Event()

        async def cancelled_owner():
            async with reconnector.suspended():
                entered.set()
                await asyncio.Future()

        owner = asyncio.create_task(cancelled_owner())
        await entered.wait()
        owner.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await owner
        self.assertEqual(0, reconnector._suspend_count)
        await reconnector.disable()

    async def test_disable_and_reenable_preserve_an_outstanding_suspension(self):
        reconnector, connector, _, _, attempt = self.make_reconnector()
        connector.current_state = state_named("Error")
        scope = reconnector.suspended()
        await scope.__aenter__()
        try:
            reconnector.enable()
            self.assertIsNone(reconnector._retry_task)
            await reconnector.disable()
            self.assertEqual(1, reconnector._suspend_count)
            reconnector.enable()
            self.assertIsNone(reconnector._retry_task)
        finally:
            await scope.__aexit__(None, None, None)

        self.assertEqual(0, reconnector._suspend_count)
        self.assertIsNotNone(reconnector._retry_task)
        await reconnector.disable()

    async def test_failed_enable_does_not_leak_its_callers_suspension(self):
        reconnector, connector, _, _, attempt = self.make_reconnector()
        connector.current_state = state_named("Disconnected")
        connector.register.side_effect = [RuntimeError("observer failure"), None]

        with self.assertRaisesRegex(RuntimeError, "observer failure"):
            async with reconnector.suspended():
                reconnector.enable()
        self.assertEqual(0, reconnector._suspend_count)

        async with reconnector.suspended():
            reconnector.enable()
        self.assertTrue(reconnector.enabled)
        self.assertEqual(0, reconnector._suspend_count)
        await reconnector.disable()

    async def test_authentication_error_is_not_retried(self):
        reconnector, connector, _, messages, attempt = self.make_reconnector(
            event_name="AuthDenied"
        )

        reconnector.enable()
        await self.let_tasks_run()

        attempt.assert_not_awaited()
        self.assertIn("Automatic reconnection is unavailable for this error", messages)
        await reconnector.disable()

    async def test_core_authentication_expiry_stops_retry_and_expires_owner(self):
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        expire_session = AsyncMock(side_effect=RuntimeError("session retired"))
        reconnector, connector, _, messages, attempt = self.make_reconnector(
            authentication_epoch_source=lambda: 7,
            authentication_epoch_validator=lambda epoch: epoch == 7,
            authentication_error_callback=expire_session,
        )
        attempt.side_effect = expired_error()

        reconnector.enable()
        await self.wait_until(
            lambda: expire_session.await_count == 1,
            "The reconnect authentication failure was not classified",
        )
        await self.let_tasks_run()

        expire_session.assert_awaited_once()
        error, epoch = expire_session.await_args.args
        self.assertIsInstance(error, expired_error)
        self.assertEqual(7, epoch)
        self.assertEqual(1, attempt.await_count)
        self.assertNotIn("Reconnection failed", messages)
        await reconnector.disable()

    async def test_disable_quiesces_retries_when_observer_unregistration_fails(self):
        session_probe = FakeSessionProbe()
        reconnector, connector, _, _, attempt = self.make_reconnector(
            session_probe=session_probe
        )
        reconnector.enable()
        connector.unregister.side_effect = RuntimeError("observer failure")

        with self.assertRaisesRegex(RuntimeError, "observer failure"):
            await reconnector.disable()

        self.assertFalse(reconnector.enabled)
        session_probe.close.assert_awaited_once_with()

    async def test_enable_registration_failure_remains_retryable(self):
        reconnector, connector, _, _, attempt = self.make_reconnector()
        connector.register.side_effect = [RuntimeError("observer failure"), None]

        with self.assertRaisesRegex(RuntimeError, "observer failure"):
            reconnector.enable()

        self.assertFalse(reconnector.enabled)
        reconnector.enable()
        self.assertTrue(reconnector.enabled)
        self.assertEqual(2, connector.register.call_count)
        await reconnector.disable()

    async def test_expired_certificate_requests_refresh(self):
        reconnector, connector, refresher, _, attempt = self.make_reconnector(
            event_name="ExpiredCertificate"
        )

        reconnector.enable()
        await self.let_tasks_run()

        refresher.force_refresh_certificate.assert_called_once_with()
        attempt.assert_not_awaited()
        await reconnector.disable()

    async def test_waits_for_network_before_retrying(self):
        network_probe = AsyncMock(side_effect=[False, True])
        reconnector, connector, _, messages, attempt = self.make_reconnector(
            network_probe=network_probe
        )

        reconnector.enable()
        await self.let_tasks_run()

        self.assertGreaterEqual(network_probe.await_count, 2)
        attempt.assert_awaited_once()
        self.assertIn("Waiting for network connectivity…", messages)
        await reconnector.disable()

    async def test_network_probe_failure_remains_retryable(self):
        network_probe = AsyncMock(side_effect=[OSError("route failed"), True])
        reconnector, connector, _, messages, attempt = self.make_reconnector(
            network_probe=network_probe
        )

        with self.assertLogs(
            "proton_vpn_kde_backend.reconnector", level="ERROR"
        ) as captured:
            reconnector.enable()
            await self.let_tasks_run()

        self.assertTrue(reconnector.enabled)
        self.assertGreaterEqual(network_probe.await_count, 2)
        attempt.assert_awaited_once()
        self.assertIn("Waiting for network connectivity…", messages)
        self.assertIn("OSError", "\n".join(captured.output))
        self.assertNotIn("route failed", "\n".join(captured.output))
        await reconnector.disable()

    async def test_waits_for_previous_connection_then_retries(self):
        reconnector, connector, _, messages, attempt = self.make_reconnector(
            delay_factory=lambda _attempt: 0
        )
        previous_connection = connector.current_connection
        connector.current_connection = None

        reconnector.enable()
        await self.wait_until(
            lambda: "Waiting for the previous VPN connection…" in messages,
            "The missing previous connection was not observed",
        )

        attempt.assert_not_awaited()

        connector.current_connection = previous_connection
        await self.wait_until(
            lambda: attempt.await_count == 1,
            "The previous VPN connection was not retried",
        )

        attempt.assert_awaited_once()
        await reconnector.disable()

    async def test_disable_during_network_probe_cancels_pending_reconnect(self):
        probe_started = asyncio.Event()
        release_probe = asyncio.Event()

        async def blocking_network_probe():
            probe_started.set()
            await release_probe.wait()
            return True

        reconnector, connector, _, _, attempt = self.make_reconnector(
            network_probe=blocking_network_probe
        )

        reconnector.enable()
        await probe_started.wait()
        await reconnector.disable()
        release_probe.set()
        await self.let_tasks_run()

        self.assertFalse(reconnector.enabled)
        attempt.assert_not_awaited()

    async def test_disable_joins_cancellation_resistant_connect(self):
        connect_started = asyncio.Event()
        cancellation_seen = asyncio.Event()
        release_connect = asyncio.Event()

        async def blocked_connect(*_args):
            connect_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancellation_seen.set()
                await release_connect.wait()

        reconnector, connector, _, _, attempt = self.make_reconnector()
        attempt.side_effect = blocked_connect
        reconnector.enable()
        await connect_started.wait()
        owned_retry = reconnector._retry_task
        self.assertIsNotNone(owned_retry)

        disable_task = asyncio.create_task(reconnector.disable())
        await cancellation_seen.wait()
        await asyncio.sleep(0)

        self.assertFalse(disable_task.done())
        self.assertIs(reconnector._retry_task, owned_retry)

        release_connect.set()
        await asyncio.wait_for(disable_task, timeout=1)
        self.assertTrue(owned_retry.done())
        self.assertIsNone(reconnector._retry_task)
        self.assertFalse(reconnector.enabled)

    async def test_new_error_rearms_after_cancelled_retry_has_quiesced(self):
        first_started = asyncio.Event()
        first_cancelled = asyncio.Event()
        release_first = asyncio.Event()
        connect_calls = 0

        async def connect(*_args):
            nonlocal connect_calls
            connect_calls += 1
            if connect_calls != 1:
                return
            first_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                first_cancelled.set()
                await release_first.wait()
                raise

        reconnector, connector, _, _, attempt = self.make_reconnector()
        attempt.side_effect = connect
        reconnector.enable()
        await first_started.wait()

        connector.current_state = state_named("Connected")
        reconnector.status_update(connector.current_state)
        await first_cancelled.wait()
        connector.current_state = state_named("Error")
        reconnector.status_update(connector.current_state)
        self.assertTrue(reconnector._retry_pending)

        release_first.set()
        await self.wait_until(
            lambda: connect_calls == 2,
            "The replacement error did not rearm reconnection",
        )
        await reconnector.disable()

    async def test_reconnection_exception_text_is_not_published_or_logged(self):
        reconnector, connector, _, messages, attempt = self.make_reconnector()
        sentinel = "credential=must-not-reach-snapshot /workspace/private.py"
        attempt.side_effect = [RuntimeError(sentinel), None]

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
        reconnector, _, _, messages, attempt = self.make_reconnector(
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
            wait_for_disconnect=AsyncMock(),
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
        bus.wait_for_disconnect.assert_awaited_once_with()
        self.assertIsNone(probe._bus)
        self.assertIsNone(probe._properties)


if __name__ == "__main__":
    unittest.main()
