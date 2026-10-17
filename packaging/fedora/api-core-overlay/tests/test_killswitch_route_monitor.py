# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Offline route-monitor regressions for legacy and current Core helpers.

Only the real handler executes; all NetworkManager I/O is substituted. In
particular, subscription can deliver a configuration change before the caller
assigns its server address, and an in-flight callback can outlive teardown.
"""

import argparse
import asyncio
from concurrent.futures import Future
import importlib.util
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


MODULE = None


class AcceptsArguments:
    def __init__(self, *args, **kwargs):
        pass


class FakeNetworkManager:
    def __init__(self, active=None, *, notify_on_subscribe=False, notify_on_add=False):
        self.callback = None
        self.route_calls = []
        self.active = active
        self.monitoring = False
        self.notify_on_subscribe = notify_on_subscribe
        self.notify_on_add = notify_on_add

    def is_monitoring_network_config_changes(self):
        return self.monitoring

    def start_monitoring_network_config_changes(self, callback):
        self.callback = callback
        self.monitoring = True
        if self.notify_on_subscribe:
            callback(self.active)

    def stop_monitoring_network_config_changes(self):
        self.monitoring = False

    def get_routable_devices(self):
        return self.active.get_devices()

    # Core 5.8.3 uses the older device accessor and passes the gateway as a
    # positional callback argument. Neither is part of the address invariant.
    get_physical_devices = get_routable_devices
    get_active_devices = get_routable_devices

    def add_route_to_device(self, device, new_server_ip, *args, **kwargs):
        self.route_calls.append((device, new_server_ip))
        result = Future()
        if self.notify_on_add:
            self.notify_on_add = False
            # Deliver the self-notification while the first route application
            # is pending, matching the original outage incident's ordering.
            loop = asyncio.get_running_loop()
            loop.call_soon(self.callback, self.active)
            loop.call_soon(result.set_result, None)
        else:
            result.set_result(None)
        return result

    def remove_route_from_device(self, device, server_ip):
        result = Future()
        result.set_result(None)
        return result


def active_connection():
    device = SimpleNamespace(get_iface=lambda: "eth0")
    return SimpleNamespace(
        get_devices=lambda: [device],
        get_ip4_config=lambda: SimpleNamespace(get_gateway=lambda: "192.0.2.1"),
    )


class RouteMonitorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        if MODULE is None:
            self.skipTest(
                "Explicit Core helper required; RPM %check runs this file with --root"
            )

    async def test_initial_self_notification_cannot_add_an_empty_route(self):
        network_manager = FakeNetworkManager()
        handler = MODULE.KillSwitchConnectionHandler(
            nm_client=network_manager
        )
        handler._start_monitoring_network_config_changes()
        device = SimpleNamespace(get_iface=lambda: "eth0")
        active = SimpleNamespace(
            get_devices=lambda: [device],
            get_ip4_config=lambda: SimpleNamespace(
                get_gateway=lambda: "192.0.2.1"
            ),
        )

        network_manager.callback(active)
        await asyncio.sleep(0)
        self.assertEqual([], network_manager.route_calls)

        handler._server_ip = "198.51.100.7"
        network_manager.callback(active)
        await asyncio.sleep(0)
        self.assertEqual(
            [(device, "198.51.100.7")],
            network_manager.route_calls,
        )

    def handler(self, network_manager):
        handler = MODULE.KillSwitchConnectionHandler(nm_client=network_manager)
        handler._ensure_connectivity_check_is_disabled = AsyncMock()
        handler._wait_for_vpn_server_route = AsyncMock()
        return handler

    async def test_subscription_notification_cannot_add_an_empty_route(self):
        network_manager = FakeNetworkManager(
            active_connection(), notify_on_subscribe=True
        )
        handler = self.handler(network_manager)
        await handler.add_vpn_server_route("198.51.100.7")
        await asyncio.sleep(0)
        self.assertEqual(
            ["198.51.100.7"], [ip for _, ip in network_manager.route_calls]
        )

    async def test_pending_route_self_notification_uses_only_owned_address(self):
        network_manager = FakeNetworkManager(active_connection(), notify_on_add=True)
        handler = self.handler(network_manager)
        await handler.add_vpn_server_route("198.51.100.7")
        await asyncio.sleep(0)
        self.assertTrue(network_manager.route_calls)
        self.assertEqual(
            {"198.51.100.7"}, {ip for _, ip in network_manager.route_calls}
        )

    async def test_in_flight_notification_after_teardown_is_ignored(self):
        network_manager = FakeNetworkManager(active_connection())
        handler = self.handler(network_manager)
        await handler.add_vpn_server_route("198.51.100.7")
        await handler.remove_vpn_server_route()
        self.assertFalse(network_manager.monitoring)
        self.assertIsNone(handler._server_ip)
        network_manager.route_calls.clear()
        network_manager.callback(network_manager.active)
        await asyncio.sleep(0)
        self.assertEqual([], network_manager.route_calls)

    async def test_repeated_outage_cycles_do_not_reuse_cleared_address(self):
        network_manager = FakeNetworkManager(
            active_connection(), notify_on_subscribe=True, notify_on_add=True
        )
        handler = self.handler(network_manager)
        for address in ("198.51.100.7", "198.51.100.8", "198.51.100.7"):
            network_manager.route_calls.clear()
            await handler.add_vpn_server_route(address)
            network_manager.callback(network_manager.active)
            await asyncio.sleep(0)
            self.assertEqual({address}, {ip for _, ip in network_manager.route_calls})
            await handler.remove_vpn_server_route()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--root", type=Path)
    source.add_argument("--module", type=Path)
    options, remaining = parser.parse_known_args()
    path = options.module or options.root / (
        "usr/lib64/python3.14/site-packages/proton/vpn/backend/networkmanager/"
        "killswitch/wireguard/killswitch_connection_handler.py"
    )
    stubs = {
        "proton.vpn": SimpleNamespace(logging=logging),
        "proton.vpn.backend.networkmanager.killswitch.wireguard.nmclient": (
            SimpleNamespace(NMClient=object, GatewayNotFoundError=RuntimeError)
        ),
        "proton.vpn.backend.networkmanager.killswitch.wireguard."
        "killswitch_connection": SimpleNamespace(
            KillSwitchConnection=AcceptsArguments,
            KillSwitchGeneralConfig=AcceptsArguments,
            KillSwitchIPConfig=AcceptsArguments,
        ),
    }
    spec = importlib.util.spec_from_file_location("route_monitor_candidate", path)
    MODULE = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(MODULE)
    unittest.main(argv=[str(path), *remaining])
