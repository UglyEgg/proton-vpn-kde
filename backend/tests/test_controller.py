# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import unittest

from proton_vpn_kde_backend.adapters import DemoCoreAdapter
from proton_vpn_kde_backend.controller import (
    BackendController,
    NpsSurveyResponse,
    VpnSnapshot,
    custom_dns_patch_from_json,
    settings_patch_from_json,
    split_tunneling_patch_from_json,
    validate_support_report,
)
from proton_vpn_kde_backend.errors import UserVisibleRuntimeError


class FailingDemoAdapter(DemoCoreAdapter):
    async def connect_fastest(self) -> None:
        raise RuntimeError("credential=must-not-reach-snapshot")


class FailingInitializationAdapter(DemoCoreAdapter):
    async def initialize(self, callback, server_data_callback=None):
        raise RuntimeError("credential=must-not-reach-log")


class UserVisibleFailingAdapter(DemoCoreAdapter):
    async def connect_fastest(self) -> None:
        raise UserVisibleRuntimeError(
            "Sign-out failed and the Proton session could not be restored"
        )


class CancellableOperationAdapter(DemoCoreAdapter):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()

    async def connect_fastest(self) -> None:
        self.started.set()
        await asyncio.Future()


class BlockingLogoutAdapter(DemoCoreAdapter):
    def __init__(self):
        super().__init__(nps_survey_available=True)
        self.logout_started = asyncio.Event()
        self.release_logout = asyncio.Event()
        self.close_calls = 0
        self.pending_nps_take_calls = 0

    async def logout(self) -> None:
        self.logout_started.set()
        await self.release_logout.wait()
        await super().logout()

    async def close(self) -> None:
        self.close_calls += 1
        await super().close()

    async def take_pending_nps_survey(self) -> bool:
        self.pending_nps_take_calls += 1
        return await super().take_pending_nps_survey()


class LoginRecordingAdapter(DemoCoreAdapter):
    def __init__(self):
        super().__init__(logged_in=False)
        self.login_calls = 0

    async def login(self, username: str, password: str) -> None:
        self.login_calls += 1
        await super().login(username, password)


class RecoveryMutationRecordingAdapter(DemoCoreAdapter):
    def __init__(self, auth_state: str):
        super().__init__(logged_in=False, kill_switch=2)
        self._packet_capture_active = True
        self._auth_state = auth_state
        self._snapshot = self._build_snapshot(message="Restart required")
        self.auth_calls: list[str] = []
        self.capture_stop_calls = 0

    async def login(self, username: str, password: str) -> None:
        self.auth_calls.append("login")

    async def submit_two_factor(self, code: str) -> None:
        self.auth_calls.append("submit_two_factor")

    async def cancel_login(self) -> None:
        self.auth_calls.append("cancel_login")

    async def begin_fido2(self) -> None:
        self.auth_calls.append("begin_fido2")

    async def submit_fido2_pin(self, pin: str) -> None:
        self.auth_calls.append("submit_fido2_pin")

    async def cancel_fido2(self) -> None:
        self.auth_calls.append("cancel_fido2")

    async def logout(self) -> None:
        self.auth_calls.append("logout")

    async def disable_kill_switch_for_login(self) -> None:
        self.auth_calls.append("disable_kill_switch_for_login")

    async def stop_packet_capture(self) -> None:
        self.capture_stop_calls += 1
        await super().stop_packet_capture()


class BlockingSettingsAdapter(DemoCoreAdapter):
    def __init__(self, method_name: str):
        super().__init__()
        self.method_name = method_name
        self.read_started = asyncio.Event()
        self.release_read = asyncio.Event()
        self.close_calls = 0

    async def _wait_if_selected(self, method_name: str) -> None:
        if self.method_name != method_name:
            return
        self.read_started.set()
        await self.release_read.wait()

    async def get_settings(self):
        await self._wait_if_selected("settings")
        return await super().get_settings()

    async def get_split_tunneling(self):
        await self._wait_if_selected("split")
        return await super().get_split_tunneling()

    async def get_custom_dns(self):
        await self._wait_if_selected("dns")
        return await super().get_custom_dns()

    async def close(self) -> None:
        self.close_calls += 1
        await super().close()


class BlockingSessionReadAdapter(DemoCoreAdapter):
    def __init__(self, method_name: str):
        super().__init__(nps_survey_available=True)
        self.method_name = method_name
        self.read_started = asyncio.Event()
        self.release_read = asyncio.Event()

    async def _wait_if_selected(self, method_name: str) -> None:
        if self.method_name != method_name:
            return
        self.read_started.set()
        await self.release_read.wait()

    async def get_countries(self):
        await self._wait_if_selected("countries")
        return await super().get_countries()

    async def get_server_groups(self, country_code: str):
        await self._wait_if_selected("groups")
        return await super().get_server_groups(country_code)

    async def get_group_servers(
        self, country_code: str, group_kind: str, group_name: str
    ):
        await self._wait_if_selected("servers")
        return await super().get_group_servers(
            country_code, group_kind, group_name
        )

    async def get_server_loads(self, country_code: str):
        await self._wait_if_selected("loads")
        return await super().get_server_loads(country_code)

    async def search_locations(self, query: str):
        await self._wait_if_selected("search")
        return await super().search_locations(query)

    async def take_pending_nps_survey(self) -> bool:
        await self._wait_if_selected("nps")
        return await super().take_pending_nps_survey()


class BlockingNpsSubmissionAdapter(DemoCoreAdapter):
    def __init__(self):
        super().__init__(nps_survey_available=True)
        self.submission_started = asyncio.Event()
        self.release_submission = asyncio.Event()
        self.close_calls = 0

    async def submit_nps_survey(self, response: NpsSurveyResponse) -> None:
        self.submission_started.set()
        await self.release_submission.wait()
        await super().submit_nps_survey(response)

    async def close(self) -> None:
        self.close_calls += 1
        await super().close()


class BlockingPacketCaptureAdapter(DemoCoreAdapter):
    def __init__(self):
        super().__init__()
        self.capture_start_started = asyncio.Event()
        self.capture_start_compensated = asyncio.Event()
        self.capture_stop_calls = 0

    async def start_packet_capture(self, directory_path: str) -> None:
        if not directory_path.startswith("/"):
            raise ValueError("Select a valid packet-capture folder")
        self._packet_capture_active = True
        self.capture_start_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self._packet_capture_active = False
            self.capture_start_compensated.set()
            raise

    async def stop_packet_capture(self) -> None:
        self.capture_stop_calls += 1
        await super().stop_packet_capture()


class BlockingSettingsMutationAdapter(DemoCoreAdapter):
    def __init__(self):
        super().__init__()
        self.settings_update_started = asyncio.Event()
        self.release_settings_update = asyncio.Event()
        self.capture_stop_calls = 0
        self._packet_capture_active = True
        self._snapshot = self._build_snapshot(
            state="connected", server_name="US#FASTEST"
        )

    async def update_settings(self, patch):
        self.settings_update_started.set()
        await self.release_settings_update.wait()
        return await super().update_settings(patch)

    async def stop_packet_capture(self) -> None:
        self.capture_stop_calls += 1
        await super().stop_packet_capture()


class BackendControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.controller = BackendController(DemoCoreAdapter())
        self.snapshots: list[VpnSnapshot] = []
        self.controller.subscribe(self.snapshots.append)
        self.assertTrue(await self.controller.start())

    async def test_start_publishes_ready_disconnected_snapshot(self):
        snapshot = self.controller.snapshot

        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.logged_in)
        self.assertEqual("disconnected", snapshot.state)
        self.assertEqual(1, snapshot.schema_version)

    async def test_startup_failure_logs_only_exception_class(self):
        controller = BackendController(FailingInitializationAdapter())

        with self.assertLogs(
            "proton_vpn_kde_backend.controller", level="ERROR"
        ) as captured:
            started = await controller.start()

        self.assertFalse(started)
        self.assertFalse(controller.snapshot.ready)
        self.assertEqual("error", controller.snapshot.state)
        self.assertEqual("Backend initialization failed", controller.snapshot.message)
        output = "\n".join(captured.output)
        self.assertIn("RuntimeError", output)
        self.assertNotIn("credential=", output)

    async def test_login_cannot_race_backend_initialization(self):
        adapter = LoginRecordingAdapter()
        controller = BackendController(adapter)

        with self.assertRaisesRegex(RuntimeError, "backend is not ready"):
            await controller.login("demo-user", "password")

        self.assertEqual(0, adapter.login_calls)
        self.assertFalse(controller.snapshot.busy)

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

    async def test_capability_connect_uses_a_validated_specialty(self):
        await self.controller.connect_fastest_with_features([" Streaming ", "P2P"])
        self.assertEqual("CH#101", self.controller.snapshot.server_name)
        self.assertTrue(self.controller.snapshot.p2p)
        self.assertTrue(self.controller.snapshot.streaming)

        await self.controller.disconnect()
        await self.controller.connect_fastest_with_features(["secure-core", "p2p"])
        self.assertEqual("CH-DE#1", self.controller.snapshot.server_name)
        self.assertTrue(self.controller.snapshot.secure_core)
        self.assertTrue(self.controller.snapshot.p2p)

        await self.controller.disconnect()
        await self.controller.connect_country_with_features("CH", ["p2p", "streaming"])
        self.assertEqual("CH#101", self.controller.snapshot.server_name)

        await self.controller.disconnect()
        await self.controller.connect_group_with_features(
            "CH", "secure-core", "Via Secure Core", ["secure-core", "p2p"]
        )
        self.assertEqual("CH-DE#1", self.controller.snapshot.server_name)

        with self.assertRaisesRegex(ValueError, "supported Proton server capabilities"):
            await self.controller.connect_fastest_with_features(["random"])

    async def test_connecting_tunnel_can_be_cancelled_concurrently(self):
        connection = asyncio.create_task(self.controller.connect_fastest())
        for _ in range(20):
            if self.controller.snapshot.state == "connecting":
                break
            await asyncio.sleep(0)

        self.assertEqual("connecting", self.controller.snapshot.state)
        self.assertTrue(self.controller.snapshot.busy)

        await self.controller.disconnect()
        await connection

        self.assertEqual("disconnected", self.controller.snapshot.state)
        self.assertFalse(self.controller.snapshot.busy)
        states = [snapshot.state for snapshot in self.snapshots]
        disconnecting_index = states.index("disconnecting")
        self.assertNotIn("connected", states[disconnecting_index + 1 :])

    async def test_snapshot_json_uses_stable_external_field_names(self):
        payload = self.controller.snapshot.to_json()

        self.assertIn('"schemaVersion":1', payload)
        self.assertIn('"startupCompatible":true', payload)
        self.assertIn('"loggedIn":true', payload)
        self.assertIn('"serverName":""', payload)
        self.assertIn('"forwardedPort":0', payload)
        self.assertIn('"packetCaptureActive":false', payload)
        self.assertIn('"coreMemoryOptimized":true', payload)
        self.assertIn('"coreVersion":"demo"', payload)
        self.assertIn('"killSwitch":0', payload)
        self.assertIn('"errorCode":""', payload)

    async def test_packet_capture_lifecycle_is_reflected_in_snapshot(self):
        await self.controller.update_settings_json('{"protocol":"protun-udp"}')
        await self.controller.connect_fastest()

        await self.controller.start_packet_capture("/tmp")
        self.assertTrue(self.controller.snapshot.packet_capture_active)

        await self.controller.stop_packet_capture()
        self.assertFalse(self.controller.snapshot.packet_capture_active)

    async def test_packet_capture_stop_preempts_and_compensates_pending_start(self):
        adapter = BlockingPacketCaptureAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        capture_start = asyncio.create_task(
            controller.start_packet_capture("/tmp")
        )
        await adapter.capture_start_started.wait()
        self.assertTrue(controller.snapshot.busy)

        await controller.stop_packet_capture()

        with self.assertRaises(asyncio.CancelledError):
            await capture_start
        self.assertTrue(adapter.capture_start_compensated.is_set())
        self.assertEqual(1, adapter.capture_stop_calls)
        self.assertFalse(adapter._packet_capture_active)
        self.assertFalse(controller.snapshot.busy)

    async def test_rejected_second_capture_start_preserves_stop_preemption(self):
        adapter = BlockingPacketCaptureAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        capture_start = asyncio.create_task(
            controller.start_packet_capture("/tmp")
        )
        await adapter.capture_start_started.wait()

        with self.assertRaisesRegex(RuntimeError, "already in progress"):
            await controller.start_packet_capture("/tmp")
        await controller.stop_packet_capture()

        with self.assertRaises(asyncio.CancelledError):
            await capture_start
        self.assertTrue(adapter.capture_start_compensated.is_set())
        self.assertEqual(1, adapter.capture_stop_calls)
        self.assertFalse(adapter._packet_capture_active)
        self.assertFalse(controller.snapshot.busy)

    async def test_capture_stop_queues_behind_same_session_settings_mutation(self):
        adapter = BlockingSettingsMutationAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        settings_update = asyncio.create_task(
            controller.update_settings_json('{"ipv6":true}')
        )
        await adapter.settings_update_started.wait()
        capture_stop = asyncio.create_task(controller.stop_packet_capture())
        await asyncio.sleep(0)

        self.assertFalse(capture_stop.done())
        self.assertEqual(0, adapter.capture_stop_calls)
        adapter.release_settings_update.set()
        await settings_update
        await capture_stop

        self.assertEqual(1, adapter.capture_stop_calls)
        self.assertFalse(controller.snapshot.packet_capture_active)

    async def test_queued_capture_stop_rejects_replacement_session(self):
        adapter = BlockingSettingsMutationAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        settings_update = asyncio.create_task(
            controller.update_settings_json('{"ipv6":true}')
        )
        await adapter.settings_update_started.wait()
        capture_stop = asyncio.create_task(controller.stop_packet_capture())
        await asyncio.sleep(0)
        adapter._logged_in = False
        adapter._auth_state = "signed_out"
        adapter._publish(
            adapter._build_snapshot(
                state="connected", server_name="US#FASTEST"
            )
        )

        adapter.release_settings_update.set()
        await settings_update
        with self.assertRaisesRegex(RuntimeError, "session changed"):
            await capture_stop
        self.assertEqual(0, adapter.capture_stop_calls)
        self.assertTrue(adapter._packet_capture_active)

    async def test_capture_stop_remains_available_after_session_expiry(self):
        adapter = BlockingSettingsMutationAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())
        adapter._logged_in = False
        adapter._auth_state = "expired"
        adapter._publish(
            adapter._build_snapshot(
                state="connected", server_name="US#FASTEST"
            )
        )

        await controller.stop_packet_capture()

        self.assertEqual(1, adapter.capture_stop_calls)
        self.assertFalse(controller.snapshot.logged_in)
        self.assertFalse(controller.snapshot.packet_capture_active)

    async def test_support_report_is_validated_and_submitted(self):
        description = "A sufficiently detailed description of the VPN issue I found."

        await self.controller.submit_support_report(
            " demo-user ",
            " user@example.com ",
            f" {description} ",
            "false",
        )

        self.assertEqual(
            "demo-user", self.controller._adapter.last_support_report.username
        )
        self.assertFalse(self.controller._adapter.last_support_report.include_logs)
        self.assertEqual(
            "Your issue has been reported", self.controller.snapshot.message
        )

    async def test_pending_nps_survey_is_taken_and_submitted_once(self):
        adapter = DemoCoreAdapter(nps_survey_available=True)
        controller = BackendController(adapter)
        await controller.start()

        self.assertIn(
            '"available":true', await controller.get_pending_nps_survey_json()
        )
        self.assertIn(
            '"available":false', await controller.get_pending_nps_survey_json()
        )
        await controller.submit_nps_survey("9", "Works well on Plasma", "submit")

        self.assertEqual(
            NpsSurveyResponse(score=9, comments="Works well on Plasma"),
            adapter.last_nps_response,
        )
        with self.assertRaisesRegex(ValueError, "0 through 10"):
            await controller.submit_nps_survey("11", "", "submit")

    async def test_accepted_nps_submission_serializes_session_replacement(self):
        adapter = BlockingNpsSubmissionAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        submission = asyncio.create_task(
            controller.submit_nps_survey("9", "Works well on Plasma", "submit")
        )
        await adapter.submission_started.wait()

        logout = asyncio.create_task(controller.logout())
        await asyncio.sleep(0)
        self.assertFalse(logout.done())
        adapter.release_submission.set()
        await submission
        await logout

        self.assertEqual(
            NpsSurveyResponse(score=9, comments="Works well on Plasma"),
            adapter.last_nps_response,
        )
        self.assertFalse(controller.snapshot.logged_in)

    async def test_nps_submission_does_not_block_vpn_operations(self):
        adapter = BlockingNpsSubmissionAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())
        await controller.connect_fastest()

        submission = asyncio.create_task(
            controller.submit_nps_survey("9", "Works well on Plasma", "submit")
        )
        await adapter.submission_started.wait()

        await controller.disconnect()
        await controller.connect_fastest()
        self.assertEqual("connected", controller.snapshot.state)

        adapter.release_submission.set()
        await submission

    async def test_nps_submission_waiting_behind_logout_has_no_side_effect(self):
        adapter = BlockingLogoutAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        logout = asyncio.create_task(controller.logout())
        await adapter.logout_started.wait()
        submission = asyncio.create_task(
            controller.submit_nps_survey("9", "Account A private comment", "submit")
        )
        await asyncio.sleep(0)
        self.assertIsNone(adapter.last_nps_response)

        adapter.release_logout.set()
        await logout

        with self.assertRaisesRegex(RuntimeError, "session changed"):
            await submission
        self.assertIsNone(adapter.last_nps_response)

    def test_support_report_rejects_invalid_or_oversized_fields(self):
        with self.assertRaisesRegex(ValueError, "valid email"):
            validate_support_report("user", "invalid", "x" * 50, "true")
        with self.assertRaisesRegex(ValueError, "at least 50"):
            validate_support_report("user", "user@example.com", "too short", "true")
        with self.assertRaisesRegex(ValueError, "log choice"):
            validate_support_report("user", "user@example.com", "x" * 50, "yes")

    async def test_location_payloads_are_versioned_and_validated(self):
        countries = await self.controller.get_countries_json()
        groups = await self.controller.get_server_groups_json(" ch ")
        group_servers = await self.controller.get_group_servers_json(
            " ch ", "secure-core", "Via Secure Core"
        )
        loads = await self.controller.get_server_loads_json(" ch ")
        location_search = await self.controller.search_locations_json(" zur ")
        server_search = await self.controller.search_locations_json(" CH# ")

        self.assertIn('"schemaVersion":1', countries)
        self.assertIn('"code":"CH"', countries)
        self.assertIn('"serverCount":4', countries)
        self.assertIn('"kind":"secure-core"', groups)
        self.assertIn('"secureCore":true', groups)
        self.assertIn('"entryCountry":"DE"', group_servers)
        self.assertIn('"loads"', loads)
        self.assertIn('"load":24', loads)
        self.assertIn('"kind":"location"', location_search)
        self.assertIn('"name":"Zurich"', location_search)
        self.assertIn('"kind":"server"', server_search)
        self.assertIn('"name":"CH#101"', server_search)

        with self.assertRaisesRegex(ValueError, "Invalid country code"):
            await self.controller.get_server_groups_json("Switzerland")
        with self.assertRaisesRegex(ValueError, "Invalid Proton server group"):
            await self.controller.get_group_servers_json("CH", "onion", "Zurich")
        with self.assertRaisesRegex(ValueError, "valid location search"):
            await self.controller.search_locations_json("   ")

    async def test_targeted_connect_methods_use_normalized_identifiers(self):
        await self.controller.connect_country(" us ")
        self.assertEqual("US#FASTEST", self.controller.snapshot.server_name)

        await self.controller.connect_server(" US-NY#88 ")
        self.assertEqual("US-NY#88", self.controller.snapshot.server_name)

        await self.controller.connect_group("CH", "location", "Zurich")
        self.assertEqual("CH#101", self.controller.snapshot.server_name)

    async def test_connected_snapshot_exposes_assigned_forwarded_port(self):
        await self.controller.update_settings_json('{"portForwarding":true}')
        await self.controller.connect_server("CH-DE#1")

        snapshot = self.controller.snapshot
        self.assertEqual(51820, snapshot.forwarded_port)
        self.assertEqual("CH", snapshot.exit_country)
        self.assertEqual("DE", snapshot.entry_country)
        self.assertTrue(snapshot.secure_core)

    async def test_reconnection_preference_is_reflected_in_snapshot(self):
        await self.controller.set_reconnection_enabled(False)

        self.assertFalse(self.controller.snapshot.reconnect_enabled)
        self.assertIn('"reconnectEnabled":false', self.controller.snapshot.to_json())

    async def test_settings_payload_is_versioned_and_updates_atomically(self):
        events = []
        self.controller.subscribe_settings(events.append)

        initial = await self.controller.get_settings_json()
        updated = await self.controller.update_settings_json(
            '{"netShield":2,"vpnAccelerator":false}'
        )

        self.assertIn('"schemaVersion":1', initial)
        self.assertIn('"protocols"', initial)
        self.assertIn('"netShield":2', updated)
        self.assertIn('"vpnAccelerator":false', updated)
        self.assertEqual(2, events[-1].net_shield)
        self.assertFalse(events[-1].vpn_accelerator)

    async def test_late_settings_reads_are_rejected_after_logout(self):
        cases = (
            ("settings", "get_settings_json", "subscribe_settings"),
            ("split", "get_split_tunneling_json", "subscribe_split_tunneling"),
            ("dns", "get_custom_dns_json", "subscribe_custom_dns"),
        )
        for method_name, read_name, subscribe_name in cases:
            with self.subTest(method_name=method_name):
                adapter = BlockingSettingsAdapter(method_name)
                controller = BackendController(adapter)
                publications = []
                getattr(controller, subscribe_name)(publications.append)
                self.assertTrue(await controller.start())

                read_task = asyncio.create_task(getattr(controller, read_name)())
                await adapter.read_started.wait()
                await controller.logout()
                adapter.release_read.set()

                with self.assertRaisesRegex(RuntimeError, "session changed"):
                    await read_task
                self.assertEqual([], publications)

    async def test_settings_reads_and_writes_have_one_completion_order(self):
        cases = (
            (
                "settings",
                "get_settings_json",
                "update_settings_json",
                '{"netShield":2}',
                "subscribe_settings",
            ),
            (
                "split",
                "get_split_tunneling_json",
                "update_split_tunneling_json",
                '{"excludeAppPaths":["/usr/bin/firefox"]}',
                "subscribe_split_tunneling",
            ),
            (
                "dns",
                "get_custom_dns_json",
                "update_custom_dns_json",
                '{"servers":[{"address":"1.1.1.1","enabled":true}]}',
                "subscribe_custom_dns",
            ),
        )
        for method_name, read_name, update_name, patch, subscribe_name in cases:
            with self.subTest(method_name=method_name):
                adapter = BlockingSettingsAdapter(method_name)
                controller = BackendController(adapter)
                publications = []
                getattr(controller, subscribe_name)(publications.append)
                self.assertTrue(await controller.start())

                read = asyncio.create_task(getattr(controller, read_name)())
                await adapter.read_started.wait()
                update = asyncio.create_task(
                    getattr(controller, update_name)(patch)
                )
                await asyncio.sleep(0)

                self.assertFalse(update.done())
                self.assertEqual([], publications)
                adapter.release_read.set()
                await read
                await update

                self.assertEqual(1, len(publications))

    async def test_late_account_scoped_reads_are_rejected_after_logout(self):
        cases = (
            ("countries", "get_countries_json", ()),
            ("groups", "get_server_groups_json", ("CH",)),
            (
                "servers",
                "get_group_servers_json",
                ("CH", "location", "Zurich"),
            ),
            ("loads", "get_server_loads_json", ("CH",)),
            ("search", "search_locations_json", ("Zurich",)),
        )
        for method_name, read_name, arguments in cases:
            with self.subTest(method_name=method_name):
                adapter = BlockingSessionReadAdapter(method_name)
                controller = BackendController(adapter)
                self.assertTrue(await controller.start())

                read_task = asyncio.create_task(
                    getattr(controller, read_name)(*arguments)
                )
                await adapter.read_started.wait()
                await controller.logout()
                adapter.release_read.set()

                with self.assertRaisesRegex(RuntimeError, "session changed"):
                    await read_task

    async def test_accepted_pending_nps_take_serializes_session_replacement(self):
        adapter = BlockingSessionReadAdapter("nps")
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        pending_survey = asyncio.create_task(
            controller.get_pending_nps_survey_json()
        )
        await adapter.read_started.wait()
        logout = asyncio.create_task(controller.logout())
        await asyncio.sleep(0)
        self.assertFalse(logout.done())

        adapter.release_read.set()
        self.assertIn('"available":true', await pending_survey)
        await logout
        self.assertFalse(controller.snapshot.logged_in)

    async def test_pending_nps_take_does_not_block_vpn_operations(self):
        adapter = BlockingSessionReadAdapter("nps")
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        pending_survey = asyncio.create_task(
            controller.get_pending_nps_survey_json()
        )
        await adapter.read_started.wait()

        await controller.connect_fastest()
        await controller.disconnect()
        self.assertEqual("disconnected", controller.snapshot.state)

        adapter.release_read.set()
        self.assertIn('"available":true', await pending_survey)

    async def test_vpn_operation_does_not_block_pending_nps_take(self):
        adapter = CancellableOperationAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        connection = asyncio.create_task(controller.connect_fastest())
        await adapter.started.wait()

        self.assertIn(
            '"available":false',
            await asyncio.wait_for(
                controller.get_pending_nps_survey_json(), timeout=1.0
            ),
        )

        connection.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await connection

    async def test_pending_nps_take_waiting_behind_logout_has_no_side_effect(self):
        adapter = BlockingLogoutAdapter()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        logout = asyncio.create_task(controller.logout())
        await adapter.logout_started.wait()
        pending_survey = asyncio.create_task(
            controller.get_pending_nps_survey_json()
        )
        await asyncio.sleep(0)
        self.assertEqual(0, adapter.pending_nps_take_calls)

        adapter.release_logout.set()
        await logout
        with self.assertRaisesRegex(RuntimeError, "session changed"):
            await pending_survey
        self.assertEqual(0, adapter.pending_nps_take_calls)

    async def test_unofficial_build_rejects_crash_reporting_enable(self):
        with self.assertRaisesRegex(RuntimeError, "unofficial community build"):
            await self.controller.update_settings_json(
                '{"anonymousCrashReports":true}'
            )

        unchanged = await self.controller.get_settings_json()
        self.assertIn('"anonymousCrashReports":false', unchanged)

    async def test_approved_build_allows_crash_reporting_preference(self):
        controller = BackendController(
            DemoCoreAdapter(), crash_report_submission_enabled=True
        )
        self.assertTrue(await controller.start())

        updated = await controller.update_settings_json(
            '{"anonymousCrashReports":true}'
        )

        self.assertIn('"anonymousCrashReports":true', updated)

    async def test_settings_patch_rejects_unknown_and_wrong_typed_values(self):
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            settings_patch_from_json('{"password":"must-not-be-accepted"}')
        with self.assertRaisesRegex(ValueError, "wrong value type"):
            settings_patch_from_json('{"killSwitch":true}')
        with self.assertRaisesRegex(ValueError, "valid NetShield"):
            settings_patch_from_json('{"netShield":9}')

    async def test_split_tunneling_payload_updates_and_syncs_scalar_settings(self):
        events = []
        settings_events = []
        self.controller.subscribe_split_tunneling(events.append)
        self.controller.subscribe_settings(settings_events.append)

        initial = await self.controller.get_split_tunneling_json()
        updated = await self.controller.update_split_tunneling_json(
            '{"excludeAppPaths":["/usr/bin/firefox"],'
            '"excludeIpRanges":["192.168.1.23/24"],"enabled":true}'
        )

        self.assertIn('"available":true', initial)
        self.assertIn('"excludeAppPaths":["/usr/bin/firefox"]', updated)
        self.assertIn('"excludeIpRanges":["192.168.1.0/24"]', updated)
        self.assertIn('"enabled":true', updated)
        self.assertEqual(("/usr/bin/firefox",), events[-1].exclude_app_paths)
        self.assertEqual(("192.168.1.0/24",), events[-1].exclude_ip_ranges)
        self.assertTrue(settings_events[-1].split_tunneling_enabled)

    async def test_split_tunneling_patch_rejects_unsafe_application_paths(self):
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            split_tunneling_patch_from_json('{"password":"no"}')
        with self.assertRaisesRegex(ValueError, "wrong type"):
            split_tunneling_patch_from_json('{"enabled":1}')
        with self.assertRaisesRegex(ValueError, "specific application"):
            split_tunneling_patch_from_json('{"excludeAppPaths":["/"]}')
        with self.assertRaisesRegex(ValueError, "cannot bypass"):
            split_tunneling_patch_from_json(
                '{"excludeAppPaths":["/usr/bin/proton-vpn-kde"]}'
            )
        with self.assertRaisesRegex(ValueError, "selected twice"):
            split_tunneling_patch_from_json(
                '{"excludeAppPaths":["/usr/bin/firefox","/usr/bin/firefox"]}'
            )
        with self.assertRaisesRegex(ValueError, "valid IPv4 or IPv6"):
            split_tunneling_patch_from_json('{"excludeIpRanges":["not-a-network"]}')
        with self.assertRaisesRegex(ValueError, "selected twice"):
            split_tunneling_patch_from_json(
                '{"excludeIpRanges":["10.0.0.1/8","10.0.0.0/8"]}'
            )

    async def test_custom_dns_payload_updates_and_syncs_scalar_settings(self):
        events = []
        settings_events = []
        self.controller.subscribe_custom_dns(events.append)
        self.controller.subscribe_settings(settings_events.append)

        initial = await self.controller.get_custom_dns_json()
        updated = await self.controller.update_custom_dns_json(
            '{"servers":[{"address":"2606:4700:4700:0:0:0:0:1111",'
            '"enabled":true}],"enabled":true}'
        )

        self.assertIn('"paidFeaturesAvailable":true', initial)
        self.assertIn('"address":"2606:4700:4700::1111"', updated)
        self.assertIn('"enabled":true', updated)
        self.assertEqual("2606:4700:4700::1111", events[-1].servers[0].address)
        self.assertTrue(settings_events[-1].custom_dns_enabled)

    async def test_custom_dns_patch_validates_addresses_and_entries(self):
        normalized = custom_dns_patch_from_json(
            '{"servers":[{"address":"2001:db8:0:0::1","enabled":false}]}'
        )
        self.assertEqual("2001:db8::1", normalized["servers"][0]["address"])

        with self.assertRaisesRegex(ValueError, "unsupported field"):
            custom_dns_patch_from_json('{"provider":"example"}')
        with self.assertRaisesRegex(ValueError, "wrong type"):
            custom_dns_patch_from_json('{"enabled":1}')
        with self.assertRaisesRegex(ValueError, "valid IPv4 or IPv6"):
            custom_dns_patch_from_json(
                '{"servers":[{"address":"dns.example","enabled":true}]}'
            )
        preserved = custom_dns_patch_from_json(
            '{"servers":['
            '{"address":"2001:db8::1","enabled":true},'
            '{"address":"2001:0db8:0:0:0:0:0:1","enabled":false}]}'
        )
        self.assertEqual(2, len(preserved["servers"]))
        self.assertEqual(
            preserved["servers"][0]["address"],
            preserved["servers"][1]["address"],
        )

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

    async def test_permanent_kill_switch_must_be_disabled_before_login(self):
        controller = BackendController(DemoCoreAdapter(logged_in=False, kill_switch=2))
        await controller.start()

        self.assertEqual(2, controller.snapshot.kill_switch)
        with self.assertRaisesRegex(RuntimeError, "permanent kill switch"):
            await controller.login("demo-user", "password")

        await controller.disable_kill_switch_for_login()
        self.assertEqual(0, controller.snapshot.kill_switch)
        await controller.login("demo-user", "password")
        self.assertTrue(controller.snapshot.logged_in)

    async def test_recovery_states_reject_every_authentication_mutation(self):
        operations = (
            lambda controller: controller.login("demo-user", "password"),
            lambda controller: controller.submit_two_factor("123456"),
            lambda controller: controller.cancel_login(),
            lambda controller: controller.begin_fido2(),
            lambda controller: controller.submit_fido2_pin("1234"),
            lambda controller: controller.cancel_fido2(),
            lambda controller: controller.logout(),
            lambda controller: controller.disable_kill_switch_for_login(),
        )
        for auth_state in (
            "authentication_unknown",
            "settings_unavailable",
            "protection_unknown",
        ):
            adapter = RecoveryMutationRecordingAdapter(auth_state)
            controller = BackendController(adapter)
            self.assertTrue(await controller.start())

            for operation in operations:
                with self.subTest(auth_state=auth_state, operation=operation):
                    with self.assertRaisesRegex(RuntimeError, "Restart the Proton"):
                        await operation(controller)

            await controller.stop_packet_capture()
            self.assertEqual(1, adapter.capture_stop_calls)
            self.assertFalse(controller.snapshot.packet_capture_active)

            self.assertEqual([], adapter.auth_calls)

    async def test_logout_disables_kill_switch(self):
        controller = BackendController(DemoCoreAdapter(kill_switch=2))
        await controller.start()

        await controller.logout()

        self.assertFalse(controller.snapshot.logged_in)
        self.assertEqual(0, controller.snapshot.kill_switch)

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

    async def test_bounded_user_visible_operation_message_is_published(self):
        controller = BackendController(UserVisibleFailingAdapter())
        await controller.start()

        with self.assertRaisesRegex(RuntimeError, "session could not be restored"):
            await controller.connect_fastest()

        self.assertEqual(
            "Sign-out failed and the Proton session could not be restored",
            controller.snapshot.message,
        )
        self.assertFalse(controller.snapshot.busy)

    async def test_cancelled_operation_always_clears_busy_state(self):
        adapter = CancellableOperationAdapter()
        controller = BackendController(adapter)
        await controller.start()
        operation = asyncio.create_task(controller.connect_fastest())
        await adapter.started.wait()
        self.assertTrue(controller.snapshot.busy)

        operation.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await operation

        self.assertFalse(controller.snapshot.busy)

    async def test_close_drains_an_accepted_mutation_before_adapter_teardown(self):
        adapter = BlockingLogoutAdapter()
        controller = BackendController(adapter)
        await controller.start()
        logout_task = asyncio.create_task(controller.logout())
        await adapter.logout_started.wait()

        close_task = asyncio.create_task(controller.close())
        await asyncio.sleep(0)
        self.assertFalse(close_task.done())
        self.assertEqual(0, adapter.close_calls)

        adapter.release_logout.set()
        await logout_task
        await close_task
        self.assertEqual(1, adapter.close_calls)

    async def test_close_drains_an_accepted_session_side_effect(self):
        adapter = BlockingNpsSubmissionAdapter()
        controller = BackendController(adapter)
        await controller.start()
        submission = asyncio.create_task(
            controller.submit_nps_survey("9", "Works well on Plasma", "submit")
        )
        await adapter.submission_started.wait()

        close_task = asyncio.create_task(controller.close())
        await asyncio.sleep(0)
        self.assertFalse(close_task.done())
        self.assertEqual(0, adapter.close_calls)

        adapter.release_submission.set()
        await submission
        await close_task
        self.assertEqual(1, adapter.close_calls)

    async def test_close_drains_an_accepted_settings_read(self):
        adapter = BlockingSettingsAdapter("settings")
        controller = BackendController(adapter)
        await controller.start()
        settings_read = asyncio.create_task(controller.get_settings_json())
        await adapter.read_started.wait()

        close_task = asyncio.create_task(controller.close())
        await asyncio.sleep(0)
        self.assertFalse(close_task.done())
        self.assertEqual(0, adapter.close_calls)

        adapter.release_read.set()
        await settings_read
        await close_task
        self.assertEqual(1, adapter.close_calls)

    async def test_close_rejects_a_queued_session_side_effect(self):
        adapter = BlockingNpsSubmissionAdapter()
        controller = BackendController(adapter)
        await controller.start()
        submission = asyncio.create_task(
            controller.submit_nps_survey("9", "Works well on Plasma", "submit")
        )
        await adapter.submission_started.wait()
        queued_read = asyncio.create_task(
            controller.get_pending_nps_survey_json()
        )
        await asyncio.sleep(0)

        close_task = asyncio.create_task(controller.close())
        await asyncio.sleep(0)
        adapter.release_submission.set()
        await submission
        with self.assertRaisesRegex(RuntimeError, "shutting down"):
            await queued_read
        await close_task
        self.assertEqual(1, adapter.close_calls)

    async def test_close_cancels_a_stuck_mutation_after_bounded_grace(self):
        adapter = CancellableOperationAdapter()
        controller = BackendController(adapter, shutdown_drain_seconds=0.01)
        await controller.start()
        operation = asyncio.create_task(controller.connect_fastest())
        await adapter.started.wait()

        await controller.close()

        self.assertTrue(operation.cancelled())
        self.assertFalse(controller.snapshot.busy)


if __name__ == "__main__":
    unittest.main()
