# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Offline regression for the initial server-route monitor race."""

import argparse
import asyncio
from concurrent.futures import Future
import importlib.util
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE = None


class AcceptsArguments:
    def __init__(self, *args, **kwargs):
        pass


class FakeNetworkManager:
    def __init__(self):
        self.callback = None
        self.route_calls = []

    def start_monitoring_network_config_changes(self, callback):
        self.callback = callback

    def add_route_to_device(self, device, server_ip, gateway):
        self.route_calls.append((device, server_ip, gateway))
        result = Future()
        result.set_result(None)
        return result


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
            [(device, "198.51.100.7", "192.0.2.1")],
            network_manager.route_calls,
        )


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
