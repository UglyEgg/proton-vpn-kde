# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Offline regression tests for the pinned Core protection activation patch.

Uses real libnm settings and fake NetworkManager operations; never constructs
an NM.Client or connects to a bus. Also suitable for porting to upstream tests.
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
from unittest.mock import patch

try:
    import gi

    require_version = getattr(gi, "require_version", None)
    if not callable(require_version):
        raise ImportError("PyGObject does not provide gi.require_version")
    require_version("NM", "1.0")
    from gi.repository import NM
except (ImportError, ValueError) as error:
    NM = None
    NM_IMPORT_ERROR = error
else:
    NM_IMPORT_ERROR = None

MODULE = None


def profile(uuid="c4c15886-3df0-42e6-8d24-623b449dafbf"):
    connection = NM.SimpleConnection.new()
    settings = NM.SettingConnection.new()
    settings.props.id = "pvpn-killswitch-ipv6"
    settings.props.uuid = uuid
    settings.props.type = "dummy"
    settings.props.interface_name = "ipv6leakintrf0"
    settings.add_permission("user", "test-user", None)
    ip4 = NM.SettingIP4Config.new()
    ip4.props.method = "disabled"
    ip6 = NM.SettingIP6Config.new()
    ip6.props.method = "manual"
    ip6.add_address(NM.IPAddress.new(10, "fdeb:446c:912d:8da::", 64))
    ip6.add_dns("::1")
    ip6.props.dns_priority = -1400
    for setting in (settings, NM.SettingDummy.new(), ip4, ip6):
        connection.add_setting(setting)
    assert connection.verify()
    return connection


class ActiveConnection:
    def __init__(self, connection, state=None):
        if state is None:
            if NM is None:
                raise RuntimeError("NetworkManager GI bindings are unavailable")
            state = NM.ActiveConnectionState.ACTIVATING
        self.connection = connection
        self.state = state
        self.handlers = {}

    def get_uuid(self):
        return self.connection.get_uuid()

    def get_state(self):
        return self.state

    def connect(self, signal, callback):
        assert signal == "state-changed"
        handler = len(self.handlers) + 1
        self.handlers[handler] = callback
        return handler

    def change_state(self, state):
        self.state = state
        for callback in list(self.handlers.values()):
            callback(self, state, 0)


class FakeNetworkManager:
    def __init__(self):
        self.profiles = []
        self.active = []
        self.add_calls = []
        self.activate_calls = []
        self.hold_add = False
        self.hold_activate = False
        self.add_reply = None
        self.activate_reply = None
        self.add_error = None
        self.activate_error = None
        self.initial_state = NM.ActiveConnectionState.ACTIVATING
        self.autoconnect_on_add = False
        self.handlers = {}

    def connect(self, signal, callback):
        # Vendor code listens for creation of a device. The reproducer's
        # device already exists, so adding a profile produces no such event.
        assert signal == "device-added"
        handler = len(self.handlers) + 1
        self.handlers[handler] = callback
        return handler

    def get_connections(self):
        # NM returns normalized profiles, including defaults absent from a
        # caller's SimpleConnection. Apply the same boundary to seeded fixtures.
        for connection in self.profiles:
            connection.normalize()
        return self.profiles

    def get_active_connections(self):
        return self.active

    def add_connection_async(self, **kwargs):
        self.add_calls.append(kwargs)
        connection = NM.SimpleConnection.new_clone(kwargs["connection"])
        connection.normalize()
        if self.add_error is None:
            self.profiles.append(connection)
            if self.autoconnect_on_add:
                self.active.append(ActiveConnection(connection, self.initial_state))
        self.add_reply = lambda: kwargs["callback"](self, connection, None)
        if not self.hold_add:
            self.add_reply()

    def add_connection_finish(self, result):
        if self.add_error:
            raise self.add_error
        return result

    def activate_connection_async(self, **kwargs):
        self.activate_calls.append(kwargs)
        active = ActiveConnection(kwargs["connection"], self.initial_state)
        self.active.append(active)
        self.activate_reply = lambda: kwargs["callback"](self, active, None)
        if not self.hold_activate:
            self.activate_reply()

    def activate_connection_finish(self, result):
        if self.activate_error:
            raise self.activate_error
        return result


class ActivationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        if MODULE is None:
            self.skipTest("Explicit Core helper required; RPM %check runs this file with --root")
        if NM is None:
            self.fail(f"NetworkManager GI bindings are unavailable: {NM_IMPORT_ERROR}")
        self.nm = FakeNetworkManager()
        self.client = MODULE.NMClient.__new__(MODULE.NMClient)
        self.client._nm_client = self.nm

        def dispatch(function, *args, **kwargs):
            future = Future()
            try:
                future.set_result(function(*args, **kwargs))
            except Exception as error:
                future.set_exception(error)
            return future

        self.client._run_on_glib_loop_thread = dispatch
        self.enterContext(patch.object(MODULE, "GObject", SimpleNamespace(
            signal_handler_disconnect=lambda obj, handler: obj.handlers.pop(handler)
        )))
        self.enterContext(patch.object(MODULE.NM.Client, "new",
                                      side_effect=AssertionError("No host NetworkManager")))

    def test_new_profile_requires_explicit_activation_and_confirmed_state(self):
        future = self.client.add_connection_async(profile(), save_to_disk=False)
        self.assertEqual(1, len(self.nm.add_calls))
        self.assertIs(False, self.nm.add_calls[0]["save_to_disk"])
        self.assertEqual(1, len(self.nm.activate_calls))
        self.assertFalse(future.done())
        active = self.nm.active[0]
        active.change_state(NM.ActiveConnectionState.ACTIVATED)
        self.assertIsNone(future.result(timeout=0.1))
        self.assertFalse(active.handlers)

    def test_existing_inactive_device_and_profile_do_not_need_device_added_signal(self):
        existing = profile("c932e212-b538-4eab-bfe8-f93b45926d48")
        existing.get_setting_connection().props.timestamp = 123
        self.nm.profiles.append(existing)
        requested = profile()
        future = self.client.add_connection_async(requested)
        self.assertFalse(self.nm.add_calls)
        self.assertIs(existing, self.nm.activate_calls[0]["connection"])
        self.assertEqual("c4c15886-3df0-42e6-8d24-623b449dafbf", requested.get_uuid())
        self.nm.active[0].change_state(NM.ActiveConnectionState.ACTIVATED)
        self.assertIsNone(future.result(timeout=0.1))

    def test_already_active_or_activating_profile_is_reused(self):
        for state in (NM.ActiveConnectionState.ACTIVATED, NM.ActiveConnectionState.ACTIVATING):
            with self.subTest(state=state):
                self.nm.profiles = [profile()]
                active = ActiveConnection(self.nm.profiles[0], state)
                self.nm.active = [active]
                future = self.client.add_connection_async(profile())
                self.assertFalse(self.nm.add_calls)
                self.assertFalse(self.nm.activate_calls)
                self.assertEqual(state == NM.ActiveConnectionState.ACTIVATED, future.done())
                active.change_state(NM.ActiveConnectionState.ACTIVATED)
                self.assertIsNone(future.result(timeout=0.1))
                self.assertFalse(active.handlers)

    def test_networkmanager_normalized_profile_matches_without_changing_request(self):
        existing = profile("c932e212-b538-4eab-bfe8-f93b45926d48")
        self.assertTrue(existing.normalize()[0])
        self.nm.profiles = [existing]
        requested = profile()
        original = requested.to_dbus(NM.ConnectionSerializationFlags.ALL)
        future = self.client.add_connection_async(requested)
        self.assertFalse(self.nm.add_calls)
        self.assertEqual(1, len(self.nm.activate_calls))
        self.assertIs(existing, self.nm.activate_calls[0]["connection"])
        self.nm.active[0].change_state(NM.ActiveConnectionState.ACTIVATED)
        self.assertIsNone(future.result(timeout=0.1))
        self.assertEqual(original, requested.to_dbus(NM.ConnectionSerializationFlags.ALL))

    def test_activation_completed_before_reply_is_detected(self):
        self.nm.initial_state = NM.ActiveConnectionState.ACTIVATED
        future = self.client.add_connection_async(profile(), save_to_disk=True)
        self.assertIsNone(future.result(timeout=0.1))
        self.assertIs(True, self.nm.add_calls[0]["save_to_disk"])
        self.assertFalse(self.nm.active[0].handlers)

    def test_autoconnect_racing_add_reply_does_not_restart_protection(self):
        self.nm.autoconnect_on_add = True
        future = self.client.add_connection_async(profile())
        self.assertFalse(self.nm.activate_calls)
        self.nm.active[0].change_state(NM.ActiveConnectionState.ACTIVATED)
        self.assertIsNone(future.result(timeout=0.1))

    def test_compatible_duplicates_prefer_the_active_profile_without_deletion(self):
        first = profile()
        second = profile("c932e212-b538-4eab-bfe8-f93b45926d48")
        self.nm.profiles = [first, second]
        self.nm.active = [ActiveConnection(second, NM.ActiveConnectionState.ACTIVATED)]
        self.assertIsNone(self.client.add_connection_async(profile()).result(timeout=0.1))
        self.assertFalse(self.nm.add_calls)
        self.assertFalse(self.nm.activate_calls)
        self.assertEqual([first, second], self.nm.profiles)

    def test_name_collision_with_different_protection_settings_is_rejected(self):
        for field in ("dns", "interface", "permissions"):
            with self.subTest(field=field):
                existing = profile()
                if field == "dns":
                    existing.get_setting_ip6_config().add_dns("2001:db8::1")
                elif field == "interface":
                    existing.get_setting_connection().props.interface_name = "unrelated0"
                else:
                    existing.get_setting_connection().add_permission("user", "other-user", None)
                self.nm.profiles = [existing]
                future = self.client.add_connection_async(profile())
                with self.assertRaisesRegex(RuntimeError, "unexpected settings"):
                    future.result(timeout=0.1)
                self.assertFalse(self.nm.add_calls)
                self.assertFalse(self.nm.activate_calls)

    def test_unrelated_profile_is_untouched(self):
        other = profile()
        other.get_setting_connection().props.id = "Unrelated VPN"
        self.nm.profiles = [other]
        future = self.client.add_connection_async(profile())
        self.assertEqual(2, len(self.nm.profiles))
        self.nm.active[0].change_state(NM.ActiveConnectionState.ACTIVATED)
        self.assertIsNone(future.result(timeout=0.1))
        self.assertEqual("Unrelated VPN", other.get_id())

    def test_failed_activation_reuses_profile_on_retry(self):
        for state in (NM.ActiveConnectionState.DEACTIVATING, NM.ActiveConnectionState.DEACTIVATED):
            future = self.client.add_connection_async(profile())
            self.nm.active[-1].change_state(state)
            with self.assertRaisesRegex(RuntimeError, "activation failed"):
                future.result(timeout=0.1)
        self.assertEqual(1, len(self.nm.add_calls))
        self.assertEqual(2, len(self.nm.activate_calls))
        self.assertEqual(1, len(self.nm.profiles))

    def test_add_and_activation_errors_complete_the_future(self):
        self.nm.add_error = RuntimeError("add failed")
        with self.assertRaisesRegex(RuntimeError, "add failed"):
            self.client.add_connection_async(profile()).result(timeout=0.1)
        self.nm.add_error = None
        self.nm.activate_error = RuntimeError("activation refused")
        with self.assertRaisesRegex(RuntimeError, "activation refused"):
            self.client.add_connection_async(profile()).result(timeout=0.1)
        self.assertFalse(self.nm.active[-1].handlers)

    async def test_timeout_cancels_glib_work_and_releases_handlers(self):
        future = self.client.add_connection_async(profile())
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(asyncio.wrap_future(future), 0.01)
        self.assertTrue(future.cancelled())
        self.assertTrue(self.nm.activate_calls[0]["cancellable"].is_cancelled())
        self.assertFalse(self.nm.active[0].handlers)
        # Do not delete protection after uncertain completion or accumulate it.
        self.assertEqual(1, len(self.nm.profiles))
        retry = self.client.add_connection_async(profile())
        self.nm.active[0].change_state(NM.ActiveConnectionState.ACTIVATED)
        self.assertIsNone(retry.result(timeout=0.1))
        self.assertEqual(1, len(self.nm.add_calls))

    def test_cancelled_add_does_not_dispatch_late_activation(self):
        self.nm.hold_add = True
        future = self.client.add_connection_async(profile())
        self.assertTrue(future.cancel())
        self.nm.add_reply()
        self.assertFalse(self.nm.activate_calls)
        self.assertTrue(self.nm.add_calls[0]["cancellable"].is_cancelled())

    def test_cancelled_activation_does_not_attach_late_handlers(self):
        self.nm.hold_activate = True
        future = self.client.add_connection_async(profile())
        self.assertTrue(future.cancel())
        self.nm.activate_reply()
        self.assertFalse(self.nm.active[0].handlers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--root", type=Path)
    source.add_argument("--module", type=Path)
    options, remaining = parser.parse_known_args()
    if NM is None:
        parser.error(f"NetworkManager GI bindings are unavailable: {NM_IMPORT_ERROR}")
    path = options.module or options.root / (
        "usr/lib64/python3.14/site-packages/proton/vpn/backend/networkmanager/"
        "killswitch/wireguard/nmclient.py"
    )
    spec = importlib.util.spec_from_file_location("activation_candidate", path)
    MODULE = importlib.util.module_from_spec(spec)
    # The helper needs only getLogger, not Proton session/import-time paths.
    with patch.dict(sys.modules, {"proton.vpn": SimpleNamespace(logging=logging)}):
        spec.loader.exec_module(MODULE)
    unittest.main(argv=[str(path), *remaining])
