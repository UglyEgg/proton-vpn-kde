# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
import unittest
from unittest.mock import AsyncMock

from dbus_fast.constants import RequestNameReply

from proton_vpn_kde_backend.__main__ import _owns_bus_name
from proton_vpn_kde_backend.controller import VpnSnapshot
from proton_vpn_kde_backend.lifetime import BackendLifetime


class FakeController:
    def __init__(self, snapshot: VpnSnapshot):
        self.snapshot = snapshot
        self._listeners: list[Callable[[VpnSnapshot], None]] = []
        self.pending_startup_recovery = False

    def subscribe(self, callback):
        self._listeners.append(callback)

    def has_pending_startup_recovery(self):
        return self.pending_startup_recovery

    def publish(self, **changes):
        self.snapshot = replace(self.snapshot, **changes)
        for callback in self._listeners:
            callback(self.snapshot)


class BackendLifetimeTests(unittest.IsolatedAsyncioTestCase):
    def make_lifetime(
        self, *, state="disconnected", ready=True, owners=None, timeout=0.02
    ):
        owners = owners if owners is not None else set()

        async def owner_probe(name):
            return name in owners

        controller = FakeController(VpnSnapshot(ready=ready, state=state))
        stopped = asyncio.Event()
        lifetime = BackendLifetime(
            controller,  # type: ignore[arg-type]
            stopped,
            owner_probe,
            idle_timeout=timeout,
        )
        return lifetime, controller, stopped, owners

    async def test_disconnected_backend_exits_after_idle_timeout(self):
        lifetime, _, stopped, _ = self.make_lifetime()

        await asyncio.wait_for(lifetime.run(), timeout=0.2)

        self.assertTrue(stopped.is_set())

    async def test_abandoned_startup_exits_after_idle_timeout(self):
        lifetime, _, stopped, _ = self.make_lifetime(state="starting", ready=False)

        await asyncio.wait_for(lifetime.run(), timeout=0.2)

        self.assertTrue(stopped.is_set())

    async def test_capture_recovery_retains_abandoned_startup(self):
        lifetime, controller, stopped, _ = self.make_lifetime(
            state="starting", ready=False
        )
        controller.pending_startup_recovery = True
        task = asyncio.create_task(lifetime.run())

        await asyncio.sleep(0.04)

        self.assertFalse(stopped.is_set())
        controller.pending_startup_recovery = False
        controller.publish(state="starting")
        await asyncio.wait_for(task, timeout=0.2)
        self.assertTrue(stopped.is_set())

    async def test_live_frontend_protects_startup_prompt(self):
        lifetime, _, stopped, owners = self.make_lifetime(state="starting", ready=False)
        owners.add(":1.42")
        await lifetime.register_client(":1.42")
        task = asyncio.create_task(lifetime.run())

        await asyncio.sleep(0.04)

        self.assertFalse(stopped.is_set())
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_vanished_frontend_releases_startup_prompt(self):
        lifetime, _, stopped, owners = self.make_lifetime(state="starting", ready=False)
        owners.add(":1.42")
        await lifetime.register_client(":1.42")
        task = asyncio.create_task(lifetime.run())
        await asyncio.sleep(0.01)
        owners.clear()
        lifetime.unregister_client(":1.42")

        await asyncio.wait_for(task, timeout=0.2)

        self.assertTrue(stopped.is_set())
        self.assertEqual(frozenset(), lifetime.clients)

    async def test_live_frontend_prevents_idle_exit(self):
        lifetime, _, stopped, owners = self.make_lifetime()
        owners.add(":1.42")
        await lifetime.register_client(":1.42")
        task = asyncio.create_task(lifetime.run())

        await asyncio.sleep(0.04)

        self.assertFalse(stopped.is_set())
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_authorized_registration_does_not_repeat_owner_probe(self):
        owner_probe = AsyncMock(return_value=True)
        controller = FakeController(VpnSnapshot(ready=True, state="disconnected"))
        lifetime = BackendLifetime(
            controller,  # type: ignore[arg-type]
            asyncio.Event(),
            owner_probe,
        )

        lifetime.register_authorized_client(":1.42")

        owner_probe.assert_not_awaited()
        self.assertEqual(frozenset({":1.42"}), lifetime.clients)

    async def test_unregister_tombstones_an_inflight_registration(self):
        probe_started = asyncio.Event()
        release_probe = asyncio.Event()

        async def delayed_owner_probe(_name: str) -> bool:
            probe_started.set()
            await release_probe.wait()
            return True

        controller = FakeController(VpnSnapshot(ready=True, state="disconnected"))
        lifetime = BackendLifetime(
            controller,  # type: ignore[arg-type]
            asyncio.Event(),
            delayed_owner_probe,
        )
        registration = asyncio.create_task(lifetime.register_client(":1.42"))
        await probe_started.wait()

        lifetime.unregister_client(":1.42")
        release_probe.set()
        await registration

        self.assertEqual(frozenset(), lifetime.clients)
        self.assertEqual({}, lifetime._client_generations)
        self.assertEqual({}, lifetime._pending_client_registrations)

    async def test_failed_registration_releases_generation_tracking(self):
        owner_probe = AsyncMock(return_value=False)
        controller = FakeController(VpnSnapshot(ready=True, state="disconnected"))
        lifetime = BackendLifetime(
            controller,  # type: ignore[arg-type]
            asyncio.Event(),
            owner_probe,
        )

        with self.assertRaisesRegex(ValueError, "has no owner"):
            await lifetime.register_client(":1.42")

        self.assertEqual({}, lifetime._client_generations)
        self.assertEqual({}, lifetime._pending_client_registrations)

    async def test_pending_registration_owns_lifetime_and_failure_starts_fresh_grace(self):
        lifetime, _, stopped, _ = self.make_lifetime(timeout=0.04)
        task = asyncio.create_task(lifetime.run())
        await asyncio.sleep(0.03)

        generation = lifetime.registration_generation(":1.42")
        await asyncio.sleep(0.03)

        self.assertFalse(stopped.is_set())
        lifetime.cancel_registration(":1.42", generation)
        await asyncio.sleep(0.02)
        self.assertFalse(stopped.is_set())

        await asyncio.wait_for(task, timeout=0.1)
        self.assertTrue(stopped.is_set())

    async def test_pending_registration_success_survives_old_deadline(self):
        lifetime, _, stopped, _ = self.make_lifetime(timeout=0.04)
        task = asyncio.create_task(lifetime.run())
        await asyncio.sleep(0.03)

        generation = lifetime.registration_generation(":1.42")
        await asyncio.sleep(0.03)
        lifetime.register_authorized_client(":1.42", generation)
        await asyncio.sleep(0.05)

        self.assertFalse(stopped.is_set())
        self.assertEqual(frozenset({":1.42"}), lifetime.clients)
        lifetime.unregister_client(":1.42")
        await asyncio.wait_for(task, timeout=0.1)

    async def test_tombstoned_pending_registrations_share_provisional_ownership(self):
        lifetime, _, stopped, _ = self.make_lifetime(timeout=0.02)
        first = lifetime.registration_generation(":1.42")
        second = lifetime.registration_generation(":1.42")
        task = asyncio.create_task(lifetime.run())

        lifetime.unregister_client(":1.42")
        lifetime.register_authorized_client(":1.42", first)
        await asyncio.sleep(0.03)

        self.assertFalse(stopped.is_set())
        self.assertEqual(frozenset(), lifetime.clients)
        lifetime.cancel_registration(":1.42", second)
        await asyncio.wait_for(task, timeout=0.1)
        self.assertEqual({}, lifetime._client_generations)
        self.assertEqual({}, lifetime._pending_client_registrations)

    async def test_registration_probe_is_bounded_and_releases_provisional_lease(self):
        never_finishes = asyncio.Event()

        async def owner_probe(_name: str) -> bool:
            await never_finishes.wait()
            return True

        controller = FakeController(VpnSnapshot(ready=True, state="disconnected"))
        lifetime = BackendLifetime(
            controller,  # type: ignore[arg-type]
            asyncio.Event(),
            owner_probe,
            registration_timeout=0.01,
        )

        with self.assertRaisesRegex(ValueError, "could not be confirmed"):
            await lifetime.register_client(":1.42")

        self.assertEqual({}, lifetime._client_generations)
        self.assertEqual({}, lifetime._pending_client_registrations)

    async def test_owner_loss_releases_frontend_before_exit(self):
        lifetime, _, stopped, owners = self.make_lifetime()
        owners.add(":1.42")
        await lifetime.register_client(":1.42")
        task = asyncio.create_task(lifetime.run())
        await asyncio.sleep(0.01)
        owners.clear()
        lifetime.unregister_client(":1.42")

        await asyncio.wait_for(task, timeout=0.2)

        self.assertTrue(stopped.is_set())
        self.assertEqual(frozenset(), lifetime.clients)

    async def test_connected_backend_survives_without_frontend(self):
        lifetime, _, stopped, _ = self.make_lifetime(state="connected")
        task = asyncio.create_task(lifetime.run())

        await asyncio.sleep(0.04)

        self.assertFalse(stopped.is_set())
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_connected_backend_does_not_poll_frontend_ownership(self):
        owner_probe = AsyncMock(return_value=True)
        controller = FakeController(VpnSnapshot(ready=True, state="connected"))
        stopped = asyncio.Event()
        lifetime = BackendLifetime(
            controller,  # type: ignore[arg-type]
            stopped,
            owner_probe,
            idle_timeout=0.02,
        )
        await lifetime.register_client(":1.42")
        task = asyncio.create_task(lifetime.run())

        await asyncio.sleep(0.04)

        owner_probe.assert_awaited_once_with(":1.42")
        self.assertFalse(stopped.is_set())
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_frontend_registration_cancels_pending_idle_exit(self):
        lifetime, _, stopped, owners = self.make_lifetime(timeout=0.1)
        task = asyncio.create_task(lifetime.run())
        await asyncio.sleep(0.01)
        owners.add(":1.42")

        await lifetime.register_client(":1.42")
        await asyncio.sleep(0.11)

        self.assertFalse(stopped.is_set())
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_disconnect_transition_starts_idle_timeout(self):
        lifetime, controller, stopped, _ = self.make_lifetime(state="connected")
        task = asyncio.create_task(lifetime.run())
        await asyncio.sleep(0.01)

        controller.publish(state="disconnected")
        await asyncio.wait_for(task, timeout=0.2)

        self.assertTrue(stopped.is_set())

    async def test_register_rejects_unowned_or_invalid_names(self):
        lifetime, _, _, _ = self.make_lifetime()

        with self.assertRaisesRegex(ValueError, "valid unique"):
            await lifetime.register_client("org.example.Frontend")
        with self.assertRaisesRegex(ValueError, "has no owner"):
            await lifetime.register_client(":1.404")

    def test_single_instance_requires_primary_ownership(self):
        self.assertTrue(_owns_bus_name(RequestNameReply.PRIMARY_OWNER))
        self.assertTrue(_owns_bus_name(RequestNameReply.ALREADY_OWNER))
        self.assertFalse(_owns_bus_name(RequestNameReply.EXISTS))
        self.assertFalse(_owns_bus_name(RequestNameReply.IN_QUEUE))
