from __future__ import annotations

import asyncio
from dataclasses import replace
import unittest

from dbus_fast.constants import RequestNameReply

from proton_vpn_kde_backend.__main__ import _owns_bus_name
from proton_vpn_kde_backend.controller import VpnSnapshot
from proton_vpn_kde_backend.lifetime import BackendLifetime


class FakeController:
    def __init__(self, snapshot: VpnSnapshot):
        self.snapshot = snapshot
        self._listeners = []

    def subscribe(self, callback):
        self._listeners.append(callback)

    def publish(self, **changes):
        self.snapshot = replace(self.snapshot, **changes)
        for callback in self._listeners:
            callback(self.snapshot)


class BackendLifetimeTests(unittest.IsolatedAsyncioTestCase):
    def make_lifetime(self, *, state="disconnected", owners=None, timeout=0.02):
        owners = owners if owners is not None else set()

        async def owner_probe(name):
            return name in owners

        controller = FakeController(VpnSnapshot(ready=True, state=state))
        stopped = asyncio.Event()
        lifetime = BackendLifetime(
            controller,  # type: ignore[arg-type]
            stopped,
            owner_probe,
            idle_timeout=timeout,
            poll_interval=0.005,
        )
        return lifetime, controller, stopped, owners

    async def test_disconnected_backend_exits_after_idle_timeout(self):
        lifetime, _, stopped, _ = self.make_lifetime()

        await asyncio.wait_for(lifetime.run(), timeout=0.2)

        self.assertTrue(stopped.is_set())

    async def test_live_frontend_prevents_idle_exit(self):
        lifetime, _, stopped, owners = self.make_lifetime()
        owners.add(":1.42")
        await lifetime.register_client(":1.42")
        task = asyncio.create_task(lifetime.run())

        await asyncio.sleep(0.04)

        self.assertFalse(stopped.is_set())
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_vanished_frontend_is_pruned_before_exit(self):
        lifetime, _, stopped, owners = self.make_lifetime()
        owners.add(":1.42")
        await lifetime.register_client(":1.42")
        owners.clear()

        await asyncio.wait_for(lifetime.run(), timeout=0.2)

        self.assertTrue(stopped.is_set())
        self.assertEqual(frozenset(), lifetime.clients)

    async def test_connected_backend_survives_without_frontend(self):
        lifetime, _, stopped, _ = self.make_lifetime(state="connected")
        task = asyncio.create_task(lifetime.run())

        await asyncio.sleep(0.04)

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
