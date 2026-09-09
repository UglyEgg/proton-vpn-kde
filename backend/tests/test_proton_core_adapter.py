# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import copy
from ipaddress import ip_address
import os
from pathlib import Path
import threading
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core_fakes import core_module_fakes

from proton_vpn_kde_backend.adapters import (
    ProtonCoreAdapter,
    _core_memory_optimization_behavior,
)
from proton_vpn_kde_backend.core_compatibility import (
    cancellable_fido2_available,
)
from proton_vpn_kde_backend.capture_recovery import (
    PACKET_CAPTURE_RECOVERY_FILENAME,
    PacketCaptureRecoveryJournal,
)
from proton_vpn_kde_backend.controller import (
    BackendController,
    NpsSurveyResponse,
    SupportReport,
)
from proton_vpn_kde_backend.errors import (
    NpsCompletionUnknownError,
    UserVisibleRuntimeError,
)
from proton_vpn_kde_backend.fido_interaction import FidoInteraction
from proton_vpn_kde_backend.reconnector import AsyncReconnector, LogindSessionProbe


def state_named(name: str):
    return type(name, (), {})()


class CoreMemoryOptimizationProbeTests(unittest.TestCase):
    @staticmethod
    def optimized_module():
        def object_hook_factory():
            shared = {}

            def share(item):
                value = item.get("Domain")
                if isinstance(value, str):
                    item["Domain"] = shared.setdefault(value, value)
                return item

            return share

        def deduplicate(logicals):
            share = object_hook_factory()
            for logical in logicals:
                share(logical)
                for physical in logical.get("Servers", ()):
                    share(physical)

        return SimpleNamespace(
            _deduplicate_server_strings=deduplicate,
            _server_string_object_hook=object_hook_factory,
        )

    def test_accepts_both_verified_string_sharing_behaviors(self):
        self.assertTrue(_core_memory_optimization_behavior(self.optimized_module()))

    def test_rejects_an_unoptimized_or_partial_core(self):
        self.assertFalse(_core_memory_optimization_behavior(SimpleNamespace()))
        self.assertFalse(
            _core_memory_optimization_behavior(
                SimpleNamespace(
                    _deduplicate_server_strings=lambda logicals: None,
                    _server_string_object_hook=lambda: lambda item: item,
                )
            )
        )

    def test_fido2_requires_an_explicit_cancellable_selection_contract(self):
        self.assertFalse(
            cancellable_fido2_available(
                SimpleNamespace(supports_fido2=True)
            )
        )
        self.assertTrue(
            cancellable_fido2_available(
                SimpleNamespace(
                    supports_fido2=True,
                    supports_cancellable_fido2_key_selection=True,
                )
            )
        )


@patch.dict("sys.modules", core_module_fakes())
class ProtonCoreAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._runtime_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._runtime_directory.cleanup)
        self._adapter_sequence = 0
        self._runtime_environment = patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": self._runtime_directory.name}
        )
        self._runtime_environment.start()
        self.addCleanup(self._runtime_environment.stop)

        # Exercise the real retry owner with explicit, desktop-independent inputs.
        def make_reconnector(*args, **kwargs):
            kwargs.setdefault("network_probe", AsyncMock(return_value=True))
            kwargs.setdefault("session_probe", SimpleNamespace(
                is_unlocked=AsyncMock(return_value=True), close=AsyncMock(),
            ))
            return AsyncReconnector(*args, **kwargs)

        self.enterContext(patch(
            "proton_vpn_kde_backend.adapters.AsyncReconnector", new=make_reconnector,
        ))
        # Fail even when production's readiness fallback catches the exception.
        for target in (
            patch("proton_vpn_kde_backend.reconnector.asyncio.create_subprocess_exec",
                  new_callable=AsyncMock, side_effect=AssertionError("Real route probe in unit test")),
            patch.object(LogindSessionProbe, "_ensure_proxy", new_callable=AsyncMock,
                         side_effect=AssertionError("Real session probe in unit test")),
        ):
            guard = self.enterContext(target)
            self.addCleanup(guard.assert_not_awaited)

    def make_api(self, *, logged_in: bool = True):
        protocol = SimpleNamespace(
            protocol="wireguard",
            ui_protocol="WireGuard",
            supports_packet_capture=Mock(return_value=False),
        )
        connector = SimpleNamespace(
            current_state=state_named("Disconnected"),
            current_connection=None,
            register=Mock(),
            unregister=Mock(),
            get_vpn_server=Mock(return_value="vpn-server"),
            connect=AsyncMock(),
            disconnect=AsyncMock(),
            iter_available_protocols=Mock(return_value=[protocol]),
            is_split_tunneling_available=True,
        )

        async def disconnect():
            connector.current_state = state_named("Disconnected")

        connector.disconnect.side_effect = disconnect
        refresher = SimpleNamespace(
            enable=AsyncMock(),
            disable=AsyncMock(),
            set_error_callback=Mock(),
            set_server_list_updated_callback=Mock(),
            set_server_loads_updated_callback=Mock(),
            set_location_names_updated_callback=Mock(),
            get_up_to_date_server_list=AsyncMock(),
            get_up_to_date_client_config=AsyncMock(return_value="client-config"),
            feature_flags={},
            notifications=SimpleNamespace(
                get_nps_survey_notifications=Mock(return_value=[])
            ),
        )
        exclude_config = SimpleNamespace(
            app_paths=["/usr/bin/firefox"],
            ip_ranges=["10.0.0.0/8"],
        )
        include_config = SimpleNamespace(app_paths=[], ip_ranges=[])
        split_tunneling = SimpleNamespace(
            enabled=False,
            mode=SimpleNamespace(value="exclude"),
            exclude=exclude_config,
            include=include_config,
        )
        split_tunneling.get_config = Mock(
            side_effect=lambda: (
                split_tunneling.exclude
                if getattr(split_tunneling.mode, "value", split_tunneling.mode)
                == "exclude"
                else split_tunneling.include
            )
        )
        settings = SimpleNamespace(
            protocol="wireguard",
            killswitch=0,
            custom_dns=SimpleNamespace(
                enabled=False,
                ip_list=[
                    SimpleNamespace(
                        ip=ip_address("9.9.9.9"),
                        enabled=False,
                    )
                ],
            ),
            ipv6=True,
            anonymous_crash_reports=False,
            features=SimpleNamespace(
                netshield=1,
                moderate_nat=False,
                vpn_accelerator=True,
                port_forwarding=False,
                split_tunneling=split_tunneling,
            ),
        )
        api = SimpleNamespace(
            get_vpn_connector=AsyncMock(return_value=connector),
            validate_connection_availability=Mock(return_value=True),
            is_user_logged_in=Mock(return_value=logged_in),
            account_name="test-user",
            account_data=SimpleNamespace(
                plan_title="VPN Plus",
                max_tier=2,
                max_connections=10,
            ),
            supports_fido2=False,
            supports_cancellable_fido2_key_selection=False,
            refresher=refresher,
            login=AsyncMock(),
            submit_2fa_code=AsyncMock(),
            generate_2fa_fido2_assertion=AsyncMock(),
            submit_2fa_fido2=AsyncMock(),
            logout=AsyncMock(),
            submit_bug_report=AsyncMock(),
            submit_nps_response=AsyncMock(),
            set_notification_seen=Mock(),
            load_settings=AsyncMock(return_value=settings),
            save_settings=AsyncMock(),
            usage_reporting=SimpleNamespace(enabled=False),
        )
        return api, connector

    def make_adapter(self, api, **kwargs):
        # Each unit-test adapter is an independent backend world. Dedicated
        # handoff tests explicitly share one journal across process generations.
        self._adapter_sequence += 1
        kwargs.setdefault(
            "account_transition_path",
            Path(self._runtime_directory.name) / f"account-{self._adapter_sequence}.json",
        )
        return ProtonCoreAdapter(api, **kwargs)

    async def start_cancellation_resistant_reconnect(self, adapter, connector):
        connect_started = asyncio.Event()
        release_connect = threading.Event()
        self.addCleanup(release_connect.set)

        async def blocked_connect(*_args):
            connect_started.set()
            await asyncio.get_running_loop().run_in_executor(
                None, release_connect.wait
            )

        async def disconnect():
            connector.current_state = state_named("Disconnected")
            adapter.status_update(connector.current_state)

        connector.connect.side_effect = blocked_connect
        connector.disconnect.side_effect = disconnect
        connector.current_connection = SimpleNamespace(
            server_id="server-id",
            server_name="",
            protocol="wireguard",
            backend="networkmanager",
        )
        adapter._api.refresher.server_list = SimpleNamespace(
            get_by_id=Mock(return_value="logical-server")
        )
        adapter._api.refresher.client_config = "client-config"
        adapter._reconnector._session_probe = SimpleNamespace(
            is_unlocked=AsyncMock(return_value=True),
            close=AsyncMock(),
        )
        connector.current_state = type("Error", (), {
            "context": SimpleNamespace(
                event=type("UnexpectedError", (), {})()
            )
        })()
        adapter._reconnector._delay_factory = lambda _attempt: 0
        adapter._reconnector.status_update(connector.current_state)
        await asyncio.wait_for(connect_started.wait(), timeout=5)
        return release_connect

    async def test_startup_compatibility_uses_official_core_check(self):
        api, _ = self.make_api()
        api.validate_connection_availability.return_value = False
        adapter = self.make_adapter(api)

        snapshot = await adapter.initialize(Mock())

        self.assertFalse(snapshot.startup_compatible)
        api.validate_connection_availability.assert_called_once_with()

    async def test_startup_compatibility_supports_fedora_core_without_helper(self):
        api, connector = self.make_api()
        del api.validate_connection_availability
        connector.iter_available_protocols.return_value = []
        adapter = self.make_adapter(api)

        snapshot = await adapter.initialize(Mock())

        self.assertFalse(snapshot.startup_compatible)
        connector.iter_available_protocols.assert_called_once_with("generic")

    async def test_packet_capture_probe_uses_fedora_protocol_group_contract(self):
        api, connector = self.make_api()
        protocol = connector.iter_available_protocols.return_value[0]
        protocol.supports_packet_capture.return_value = True
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        settings = await adapter.get_settings()

        self.assertTrue(settings.packet_capture_supported)
        self.assertTrue(
            all(
                call.args == ("generic",)
                for call in connector.iter_available_protocols.call_args_list
            )
        )

    async def test_support_report_uses_official_api_without_logs(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        await adapter.submit_support_report(
            SupportReport(
                username="test-user",
                email="user@example.com",
                description="A detailed support report that is long enough for submission.",
                include_logs=False,
            )
        )

        api.submit_bug_report.assert_awaited_once()
        form = api.submit_bug_report.await_args.args[0]
        self.assertEqual("test-user", form.username)
        self.assertEqual("KDE Plasma GUI", form.client)
        self.assertEqual([], form.attachments)

    async def test_support_authentication_expiry_retires_the_owning_session(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.submit_bug_report.side_effect = expired_error()
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await adapter.submit_support_report(
                SupportReport(
                    username="test-user",
                    email="user@example.com",
                    description=(
                        "A detailed support report that is long enough for submission."
                    ),
                    include_logs=False,
                )
            )

        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)

    async def test_nps_survey_uses_cached_notification_and_official_api(self):
        api, _ = self.make_api()
        survey = SimpleNamespace(survey_id="survey-1", seen=False, is_active=True)
        api.refresher.notifications.get_nps_survey_notifications.return_value = [survey]
        event_loop_thread = threading.get_ident()
        api.set_notification_seen.side_effect = (
            lambda _survey_id: self.assertNotEqual(
                event_loop_thread, threading.get_ident()
            )
        )
        adapter = self.make_adapter(api)
        adapter._logged_in = True

        self.assertTrue(await adapter.take_pending_nps_survey())
        api.set_notification_seen.assert_called_once_with("survey-1")

        await adapter.submit_nps_survey(
            NpsSurveyResponse(score=10, comments="Excellent")
        )
        api.submit_nps_response.assert_awaited_once()
        response = api.submit_nps_response.await_args.args[0]
        self.assertEqual(10, response.user_score)
        self.assertEqual("Excellent", response.user_comments)
        self.assertEqual("SUBMIT", response.response_type.name)

    async def test_cancelled_nps_cache_write_remains_owned_off_event_loop(self):
        api, _ = self.make_api()
        survey = SimpleNamespace(survey_id="survey-1", seen=False, is_active=True)
        api.refresher.notifications.get_nps_survey_notifications.return_value = [survey]
        write_started = threading.Event()
        release_write = threading.Event()

        def blocked_write(_survey_id):
            write_started.set()
            release_write.wait(timeout=2)

        api.set_notification_seen.side_effect = blocked_write
        adapter = self.make_adapter(api)
        adapter._logged_in = True
        survey_task = asyncio.create_task(adapter.take_pending_nps_survey())
        for _ in range(100):
            if write_started.is_set():
                break
            await asyncio.sleep(0.005)
        self.assertTrue(write_started.is_set())

        heartbeat_ran = False

        async def heartbeat():
            nonlocal heartbeat_ran
            await asyncio.sleep(0)
            heartbeat_ran = True

        await asyncio.wait_for(heartbeat(), timeout=0.1)
        self.assertTrue(heartbeat_ran)
        survey_task.cancel()
        await asyncio.sleep(0)
        self.assertFalse(survey_task.done())

        release_write.set()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(survey_task, timeout=1)
        api.set_notification_seen.assert_called_once_with("survey-1")

    async def test_nps_upstream_failure_is_completion_unknown(self):
        api, _ = self.make_api()
        api.submit_nps_response.side_effect = RuntimeError(
            "accepted before the response was lost"
        )
        adapter = self.make_adapter(api)
        adapter._logged_in = True

        with self.assertRaises(NpsCompletionUnknownError):
            await adapter.submit_nps_survey(
                NpsSurveyResponse(score=9, comments="Works well on Plasma")
            )

        api.submit_nps_response.assert_awaited_once()

    async def test_nps_authentication_expiry_is_still_completion_unknown(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.submit_nps_response.side_effect = expired_error()
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaises(NpsCompletionUnknownError):
            await adapter.submit_nps_survey(
                NpsSurveyResponse(score=8, comments="Authentication expired")
            )

        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)

    async def test_nps_side_effect_blocks_replacement_login(self):
        api, _ = self.make_api()
        submit_started = asyncio.Event()
        release_submit = asyncio.Event()

        async def blocked_submit(_response):
            submit_started.set()
            await release_submit.wait()

        api.submit_nps_response.side_effect = blocked_submit
        api.login.return_value = SimpleNamespace(
            authenticated=True,
            twofa_required=False,
        )
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        submission = asyncio.create_task(
            adapter.submit_nps_survey(
                NpsSurveyResponse(score=10, comments="Serialized")
            )
        )
        await asyncio.wait_for(submit_started.wait(), timeout=5)
        replacement_login = asyncio.create_task(
            adapter.login("replacement-user", "not-recorded")
        )
        await asyncio.sleep(0)

        api.login.assert_not_awaited()
        release_submit.set()
        await submission
        with self.assertRaisesRegex(RuntimeError, "restart the backend"):
            await asyncio.wait_for(replacement_login, timeout=1)
        api.login.assert_not_awaited()

    async def test_initialize_reuses_core_and_subscribes_without_connecting(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)

        snapshot = await adapter.initialize(Mock())

        api.get_vpn_connector.assert_awaited_once_with()
        connector.register.assert_any_call(adapter)
        self.assertEqual(2, connector.register.call_count)
        api.refresher.enable.assert_awaited_once_with()
        connector.connect.assert_not_awaited()
        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.logged_in)
        self.assertEqual("disconnected", snapshot.state)
        api.refresher.set_server_list_updated_callback.assert_called_once()
        api.refresher.set_server_loads_updated_callback.assert_called_once()
        api.refresher.set_location_names_updated_callback.assert_called_once()

    async def test_initialize_supports_core_without_location_name_callback(self):
        api, connector = self.make_api()
        del api.refresher.set_location_names_updated_callback
        adapter = self.make_adapter(api)

        snapshot = await adapter.initialize(Mock())
        self.assertTrue(snapshot.ready)
        api.refresher.set_server_list_updated_callback.assert_called_once()
        api.refresher.set_server_loads_updated_callback.assert_called_once()

        await adapter.close()
        connector.unregister.assert_any_call(adapter)

    async def test_server_refresh_callbacks_preserve_update_scope(self):
        api, _ = self.make_api()
        events = []
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock(), events.append)

        list_callback = api.refresher.set_server_list_updated_callback.call_args.args[0]
        loads_callback = api.refresher.set_server_loads_updated_callback.call_args.args[
            0
        ]
        location_names_callback = (
            api.refresher.set_location_names_updated_callback.call_args.args[0]
        )
        list_callback()
        loads_callback()
        location_names_callback()

        self.assertEqual([True, False, True], events)

    async def test_only_topology_callbacks_discard_the_search_projection(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        marker = object()
        adapter._search_projection = marker

        adapter._on_server_loads_updated()
        self.assertIs(marker, adapter._search_projection)
        self.assertEqual(0, adapter._server_list_generation)

        adapter._on_server_list_updated()
        self.assertIsNone(adapter._search_projection)
        self.assertEqual(1, adapter._server_list_generation)

        adapter._search_projection = marker
        adapter._on_location_names_updated()
        self.assertIsNone(adapter._search_projection)
        self.assertEqual(2, adapter._server_list_generation)

    async def test_secret_service_wait_does_not_block_asyncio_thread(self):
        api, connector = self.make_api()
        prompt_started = threading.Event()
        prompt_released = threading.Event()

        def wait_for_provider_approval():
            prompt_started.set()
            prompt_released.wait(timeout=2)
            return True

        api.is_user_logged_in = wait_for_provider_approval
        adapter = self.make_adapter(api)
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

    async def test_capture_recovery_uses_one_bounded_session_restore(self):
        api, connector = self.make_api()
        events: list[str] = []
        prompt_started = threading.Event()
        prompt_released = threading.Event()
        session_loaded = threading.Event()

        def wait_for_provider_approval():
            events.append("secret-prompt")
            prompt_started.set()
            prompt_released.wait(timeout=2)
            session_loaded.set()
            return True

        async def initialize_connector():
            events.append("connector")
            self.assertTrue(session_loaded.is_set())
            return connector

        async def stop_capture():
            events.append("capture-stop")

        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )
        PacketCaptureRecoveryJournal(recovery_path).store_deadline(
            time.clock_gettime(time.CLOCK_BOOTTIME) - 0.01
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = SimpleNamespace(
            server_name="US-IL#42",
            stop_packet_capture=AsyncMock(side_effect=stop_capture),
        )
        api.is_user_logged_in = wait_for_provider_approval
        api.get_vpn_connector = AsyncMock(side_effect=initialize_connector)
        adapter = ProtonCoreAdapter(
            api,
            packet_capture_recovery_path=recovery_path,
            packet_capture_stop_attempt_seconds=0.01,
        )

        initialize_task = asyncio.create_task(adapter.initialize(Mock()))
        try:
            for _ in range(100):
                if prompt_started.is_set():
                    break
                await asyncio.sleep(0.01)

            self.assertTrue(prompt_started.is_set())
            self.assertEqual(["secret-prompt"], events)
            self.assertFalse(initialize_task.done())
            self.assertTrue(recovery_path.exists())
        finally:
            prompt_released.set()

        await initialize_task
        self.assertEqual(["secret-prompt", "connector", "capture-stop"], events)
        self.assertFalse(recovery_path.exists())
        connector.current_connection.stop_packet_capture.assert_awaited_once_with()

    async def test_capture_recovery_does_not_publish_before_initialization(self):
        api, connector = self.make_api()
        refresher_started = asyncio.Event()
        refresher_released = asyncio.Event()
        snapshots = []

        async def hold_refresher_enable():
            refresher_started.set()
            await refresher_released.wait()

        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )
        PacketCaptureRecoveryJournal(recovery_path).store_deadline(
            time.clock_gettime(time.CLOCK_BOOTTIME) - 0.01
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = SimpleNamespace(
            server_name="US-IL#42",
            stop_packet_capture=AsyncMock(),
        )
        api.refresher.enable.side_effect = hold_refresher_enable
        adapter = ProtonCoreAdapter(
            api,
            packet_capture_recovery_path=recovery_path,
            packet_capture_stop_attempt_seconds=0.01,
        )

        initialize_task = asyncio.create_task(adapter.initialize(snapshots.append))
        await asyncio.wait_for(refresher_started.wait(), timeout=1)

        self.assertFalse(initialize_task.done())
        self.assertFalse(recovery_path.exists())
        self.assertEqual([], snapshots)
        adapter.status_update(connector.current_state)
        adapter._on_reconnector_status("Reconnecting")
        self.assertEqual([], snapshots)

        refresher_released.set()
        snapshot = await initialize_task
        self.assertTrue(snapshot.ready)
        self.assertTrue(snapshot.logged_in)
        self.assertEqual("signed_in", snapshot.auth_state)

        adapter.status_update(connector.current_state)
        self.assertEqual([snapshot], snapshots)

    async def test_capture_recovery_retains_journal_when_session_restore_times_out(self):
        api, _ = self.make_api()
        prompt_started = threading.Event()
        prompt_released = threading.Event()

        def wait_for_provider_approval():
            prompt_started.set()
            prompt_released.wait(timeout=2)
            return True

        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )
        PacketCaptureRecoveryJournal(recovery_path).store_deadline(
            time.clock_gettime(time.CLOCK_BOOTTIME) - 0.01
        )
        api.is_user_logged_in = wait_for_provider_approval
        adapter = self.make_adapter(api, packet_capture_recovery_path=recovery_path)

        with patch(
            "proton_vpn_kde_backend.adapters."
            "CAPTURE_RECOVERY_SESSION_TIMEOUT_SECONDS",
            0.01,
        ):
            try:
                with self.assertRaisesRegex(
                    UserVisibleRuntimeError,
                    "session restoration did not finish",
                ):
                    await adapter.initialize(Mock())
            finally:
                prompt_released.set()

        self.assertTrue(prompt_started.is_set())
        self.assertTrue(recovery_path.exists())
        api.get_vpn_connector.assert_not_awaited()

    async def test_capture_recovery_rejects_synthetic_logged_out_connector(self):
        api, _ = self.make_api(logged_in=False)
        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )
        PacketCaptureRecoveryJournal(recovery_path).store_deadline(
            time.clock_gettime(time.CLOCK_BOOTTIME) - 0.01
        )
        adapter = self.make_adapter(api, packet_capture_recovery_path=recovery_path)

        with self.assertRaisesRegex(
            UserVisibleRuntimeError,
            "session restoration is required",
        ):
            await adapter.initialize(Mock())

        self.assertTrue(recovery_path.exists())
        api.get_vpn_connector.assert_not_awaited()

    async def test_capture_recovery_retains_journal_when_connector_times_out(self):
        api, _ = self.make_api()
        connector_started = asyncio.Event()
        connector_never_finishes = asyncio.Event()

        async def wait_for_connector():
            connector_started.set()
            await connector_never_finishes.wait()

        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )
        PacketCaptureRecoveryJournal(recovery_path).store_deadline(
            time.clock_gettime(time.CLOCK_BOOTTIME) - 0.01
        )
        api.get_vpn_connector = AsyncMock(side_effect=wait_for_connector)
        adapter = self.make_adapter(api, packet_capture_recovery_path=recovery_path)

        with patch(
            "proton_vpn_kde_backend.adapters."
            "CAPTURE_RECOVERY_CONNECTOR_TIMEOUT_SECONDS",
            0.01,
        ):
            with self.assertRaisesRegex(
                UserVisibleRuntimeError,
                "did not restore the VPN connection",
            ):
                await adapter.initialize(Mock())

        self.assertTrue(connector_started.is_set())
        self.assertTrue(recovery_path.exists())
        self.assertIsNone(adapter._connector)

    async def test_logged_out_start_does_not_enable_refresher(self):
        api, _ = self.make_api(logged_in=False)
        adapter = self.make_adapter(api)

        snapshot = await adapter.initialize(Mock())

        api.refresher.enable.assert_not_awaited()
        self.assertFalse(snapshot.logged_in)
        self.assertEqual("Sign in to Proton VPN to continue", snapshot.message)

    async def test_logged_out_start_exposes_and_disables_permanent_kill_switch(self):
        api, _ = self.make_api(logged_in=False)
        settings = await api.load_settings()
        settings.killswitch = 2
        api.load_settings.reset_mock()
        adapter = self.make_adapter(api)

        snapshot = await adapter.initialize(Mock())
        self.assertEqual(2, snapshot.kill_switch)

        await adapter.disable_kill_switch_for_login()

        self.assertEqual(0, settings.killswitch)
        api.save_settings.assert_awaited_once_with(settings)

    async def test_kill_switch_disable_retry_reapplies_partially_persisted_state(self):
        api, _ = self.make_api(logged_in=False)
        settings = await api.load_settings()
        persisted_kill_switch = 2
        live_kill_switch = 2
        save_calls = 0

        async def load_settings():
            settings.killswitch = persisted_kill_switch
            return settings

        async def save_settings(saved_settings):
            nonlocal persisted_kill_switch, live_kill_switch, save_calls
            save_calls += 1
            persisted_kill_switch = saved_settings.killswitch
            if save_calls == 1:
                raise RuntimeError("connector application failed")
            live_kill_switch = saved_settings.killswitch

        api.load_settings = AsyncMock(side_effect=load_settings)
        api.save_settings = AsyncMock(side_effect=save_settings)
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "save the VPN settings"):
            await adapter.disable_kill_switch_for_login()
        self.assertEqual(0, persisted_kill_switch)
        self.assertEqual(2, live_kill_switch)
        self.assertEqual(2, adapter._kill_switch)

        await adapter.disable_kill_switch_for_login()

        self.assertEqual(2, save_calls)
        self.assertEqual(0, live_kill_switch)
        self.assertEqual(0, adapter._kill_switch)

    async def test_startup_settings_failure_blocks_login_until_state_is_known(self):
        api, _ = self.make_api(logged_in=False)
        settings = await api.load_settings()
        settings.killswitch = 2
        api.load_settings.side_effect = [RuntimeError("temporary read failure"), settings]
        snapshots = []
        adapter = self.make_adapter(api)

        initial = await adapter.initialize(snapshots.append)

        self.assertEqual("settings_unavailable", initial.auth_state)
        self.assertIn("restart", initial.message)
        with self.assertRaisesRegex(RuntimeError, "permanent kill switch"):
            await adapter.login("test-user", "not-recorded")

        self.assertEqual(2, snapshots[-1].kill_switch)
        self.assertEqual("signed_out", snapshots[-1].auth_state)
        api.login.assert_not_awaited()

    async def test_login_without_two_factor_enables_session_services(self):
        api, connector = self.make_api(logged_in=False)
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        await adapter.login("test-user", "not-recorded")

        api.login.assert_awaited_once_with("test-user", "not-recorded")
        api.refresher.enable.assert_awaited_once_with()
        self.assertTrue(snapshots[-1].logged_in)
        self.assertEqual("signed_in", snapshots[-1].auth_state)
        self.assertEqual("VPN Plus", snapshots[-1].plan_title)
        self.assertEqual(2, connector.register.call_count)

    async def test_failed_session_service_start_does_not_commit_login_state(self):
        api, _ = self.make_api(logged_in=False)
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )
        api.refresher.enable.side_effect = RuntimeError("refresh failed")
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "rolled back"):
            await adapter.login("test-user", "not-recorded")

        api.logout.assert_awaited_once_with()
        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)
        self.assertFalse(snapshots[-1].logged_in)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)
        self.assertEqual(
            "Proton session services could not start; sign-in was rolled back",
            snapshots[-1].message,
        )
        restarted = self.make_adapter(api)
        restarted_snapshot = await restarted.initialize(Mock())
        self.assertFalse(restarted_snapshot.logged_in)
        self.assertEqual("signed_out", restarted_snapshot.auth_state)

    async def test_failed_login_rollback_exposes_authenticated_degraded_state(self):
        api, _ = self.make_api(logged_in=False)
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )
        api.refresher.enable.side_effect = RuntimeError("refresh failed")
        api.logout.side_effect = RuntimeError("logout failed")
        api.is_user_logged_in.side_effect = [False, True]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "could not be cleared"):
            await adapter.login("test-user", "not-recorded")

        self.assertTrue(adapter._logged_in)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)
        self.assertIn("could not be cleared", snapshots[-1].message)

    async def test_failed_login_rollback_accepts_core_confirmed_sign_out(self):
        api, _ = self.make_api(logged_in=False)
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )
        api.refresher.enable.side_effect = RuntimeError("refresh failed")
        api.logout.side_effect = RuntimeError("late cleanup failed")
        api.is_user_logged_in.side_effect = [False, False]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "rolled back"):
            await adapter.login("test-user", "not-recorded")

        self.assertFalse(adapter._logged_in)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)

    async def test_successful_login_cleanup_does_not_hide_persisted_session(self):
        api, _ = self.make_api(logged_in=False)
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )
        api.refresher.enable.side_effect = RuntimeError("refresh failed")
        api.is_user_logged_in.side_effect = [False, True]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "could not be cleared"):
            await adapter.login("test-user", "not-recorded")

        api.logout.assert_awaited_once_with()
        self.assertTrue(adapter._logged_in)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)

    async def test_successful_login_cleanup_preserves_unknown_account_state(self):
        api, _ = self.make_api(logged_in=False)
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )
        api.refresher.enable.side_effect = RuntimeError("refresh failed")
        api.is_user_logged_in.side_effect = [
            False,
            RuntimeError("secret store unavailable"),
        ]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "could not confirm"):
            await adapter.login("test-user", "not-recorded")

        api.logout.assert_awaited_once_with()
        self.assertFalse(adapter._logged_in)
        self.assertEqual("authentication_unknown", snapshots[-1].auth_state)
        self.assertIn("restart", snapshots[-1].message)

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
        adapter = self.make_adapter(api)
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
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        await adapter.login("test-user", "super-secret")

        self.assertNotIn("super-secret", snapshots[-1].message)
        self.assertEqual(
            "Proton could not complete authentication", snapshots[-1].message
        )

    async def test_late_login_error_reconciles_core_authenticated_state(self):
        api, _ = self.make_api(logged_in=False)
        api.login.side_effect = RuntimeError("late session-data failure")
        api.is_user_logged_in.side_effect = [False, True]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        await adapter.login("test-user", "not-recorded")

        self.assertTrue(adapter._logged_in)
        self.assertEqual("signed_in", snapshots[-1].auth_state)
        self.assertIn("incomplete authentication response", snapshots[-1].message)
        api.refresher.enable.assert_awaited_once_with()

    async def test_unknown_late_login_state_is_not_published_as_signed_out(self):
        api, _ = self.make_api(logged_in=False)
        api.login.side_effect = RuntimeError("late session-data failure")
        api.is_user_logged_in.side_effect = [False, RuntimeError("store unavailable")]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "could not confirm"):
            await adapter.login("test-user", "not-recorded")

        self.assertFalse(adapter._logged_in)
        self.assertEqual("authentication_unknown", snapshots[-1].auth_state)

    async def test_cancel_login_failure_preserves_confirmed_core_session(self):
        api, _ = self.make_api(logged_in=False)
        api.logout.side_effect = RuntimeError("logout failed")
        api.is_user_logged_in.side_effect = [False, True]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "still active"):
            await adapter.cancel_login()

        self.assertTrue(adapter._logged_in)
        self.assertEqual("signed_in", snapshots[-1].auth_state)
        api.refresher.enable.assert_awaited_once_with()

    async def test_security_key_flow_uses_official_api(self):
        api, _ = self.make_api(logged_in=False)
        api.supports_fido2 = True
        api.supports_cancellable_fido2_key_selection = True
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
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)
        await adapter.login("test-user", "not-recorded")

        await adapter.begin_fido2()

        api.submit_2fa_fido2.assert_awaited_once_with("assertion")
        self.assertTrue(any(item.auth_state == "fido_touch" for item in snapshots))
        self.assertTrue(snapshots[-1].logged_in)

    async def test_security_key_flow_is_hidden_without_safe_core_contract(self):
        api, connector = self.make_api(logged_in=False)
        api.supports_fido2 = True
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)
        adapter._auth_state = "two_factor"

        snapshot = adapter._snapshot_from_state(connector.current_state)
        self.assertFalse(snapshot.fido2_available)
        with self.assertRaisesRegex(
            UserVisibleRuntimeError, "cannot safely cancel key selection"
        ):
            await adapter.begin_fido2()
        api.generate_2fa_fido2_assertion.assert_not_awaited()

    async def test_shutdown_releases_blocking_security_key_pin_worker(self):
        api, _ = self.make_api(logged_in=False)
        api.supports_fido2 = True
        api.supports_cancellable_fido2_key_selection = True
        worker_returned = threading.Event()
        interactions = []

        async def generate_assertion(interaction, _cancel_assertion):
            interactions.append(interaction)
            try:
                return await asyncio.to_thread(interaction.request_pin)
            finally:
                worker_returned.set()

        api.generate_2fa_fido2_assertion.side_effect = generate_assertion
        adapter = self.make_adapter(api)
        # Thread wake-up latency under the supported Python 3.11 floor can
        # exceed 10 ms on a loaded CI worker. Keep the test deadline bounded
        # without making scheduler jitter the behavior under test.
        controller = BackendController(adapter, shutdown_drain_seconds=0.1)
        self.assertTrue(await controller.start())
        adapter._auth_state = "two_factor"

        fido_task = asyncio.create_task(controller.begin_fido2())
        for _ in range(100):
            if controller.snapshot.auth_state == "fido_pin":
                break
            await asyncio.sleep(0.01)
        self.assertEqual("fido_pin", controller.snapshot.auth_state)

        await asyncio.wait_for(controller.close(), timeout=1.0)

        self.assertTrue(fido_task.cancelled())
        self.assertEqual(1, len(interactions))
        self.assertTrue(interactions[0].cancelled)
        self.assertTrue(worker_returned.is_set())
        self.assertIsNone(adapter._fido_interaction)

    async def test_security_key_cancel_before_pin_wait_does_not_block(self):
        loop = asyncio.get_running_loop()
        interaction = FidoInteraction(loop, Mock())

        interaction.cancel()
        pin = await asyncio.wait_for(
            asyncio.to_thread(interaction.request_pin), timeout=1.0
        )

        self.assertIsNone(pin)
        self.assertTrue(interaction.cancelled)

    async def test_security_key_cancel_during_submit_reconciles_late_login(self):
        api, _ = self.make_api(logged_in=False)
        api.supports_fido2 = True
        api.supports_cancellable_fido2_key_selection = True
        api.is_user_logged_in.side_effect = [False, True]
        api.generate_2fa_fido2_assertion.return_value = "assertion"
        submit_started = asyncio.Event()
        release_submit = asyncio.Event()

        async def late_submit_failure(_assertion):
            submit_started.set()
            await release_submit.wait()
            raise RuntimeError("late session-data failure")

        api.submit_2fa_fido2.side_effect = late_submit_failure
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)
        adapter._auth_state = "two_factor"

        fido_task = asyncio.create_task(adapter.begin_fido2())
        await asyncio.wait_for(submit_started.wait(), timeout=5)
        await adapter.cancel_fido2()
        release_submit.set()
        await fido_task

        self.assertTrue(adapter._logged_in)
        self.assertEqual("signed_in", snapshots[-1].auth_state)
        self.assertIn("incomplete authentication response", snapshots[-1].message)

    async def test_cancelled_fido_caller_joins_submission_and_reconciliation(self):
        api, _ = self.make_api(logged_in=False)
        api.supports_fido2 = True
        api.supports_cancellable_fido2_key_selection = True
        api.is_user_logged_in.side_effect = [False, True]
        api.generate_2fa_fido2_assertion.return_value = "assertion"
        submit_started = asyncio.Event()
        release_submit = asyncio.Event()

        async def late_submit_failure(_assertion):
            submit_started.set()
            await release_submit.wait()
            raise RuntimeError("late session-data failure")

        api.submit_2fa_fido2.side_effect = late_submit_failure
        adapter = self.make_adapter(api)
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())
        adapter._auth_state = "two_factor"

        fido_task = asyncio.create_task(controller.begin_fido2())
        await asyncio.wait_for(submit_started.wait(), timeout=5)
        interaction = adapter._fido_interaction
        self.assertIsNotNone(interaction)
        try:
            fido_task.cancel()
            for _ in range(10):
                if interaction.cancelled:
                    break
                await asyncio.sleep(0)
            fido_task.cancel()
            await asyncio.sleep(0)
            self.assertTrue(interaction.cancelled)
            self.assertFalse(fido_task.done())
            self.assertTrue(controller.snapshot.busy)
            self.assertTrue(adapter._authentication_scope._lock.locked())
        finally:
            release_submit.set()
            with self.assertRaises(asyncio.CancelledError):
                await fido_task

        self.assertTrue(adapter._logged_in)
        self.assertEqual("signed_in", controller.snapshot.auth_state)
        self.assertIn("incomplete authentication response", controller.snapshot.message)
        self.assertFalse(controller.snapshot.busy)
        self.assertIsNone(adapter._fido_interaction)

    async def test_fido_cancellation_before_provider_start_prevents_prompt(self):
        api, _ = self.make_api(logged_in=False)
        api.supports_fido2 = True
        api.supports_cancellable_fido2_key_selection = True
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        adapter._auth_state = "two_factor"
        child_started = asyncio.Event()
        release_child = asyncio.Event()
        authenticate = adapter._authenticate_fido2

        async def delayed_child(interaction):
            child_started.set()
            await release_child.wait()
            await authenticate(interaction)

        with patch.object(adapter, "_authenticate_fido2", delayed_child):
            fido_task = asyncio.create_task(adapter.begin_fido2())
            await asyncio.wait_for(child_started.wait(), timeout=5)
            fido_task.cancel()
            try:
                await asyncio.sleep(0)
                self.assertTrue(adapter._fido_interaction.cancelled)
                self.assertFalse(fido_task.done())
                api.generate_2fa_fido2_assertion.assert_not_called()
            finally:
                release_child.set()
                with self.assertRaises(asyncio.CancelledError):
                    await fido_task

        api.generate_2fa_fido2_assertion.assert_not_called()
        self.assertEqual("two_factor", adapter._auth_state)
        self.assertIsNone(adapter._fido_interaction)

    async def test_logout_disconnects_and_clears_account_metadata(self):
        api, connector = self.make_api()
        connector.current_state = state_named("Connected")
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        await adapter.logout()

        connector.disconnect.assert_awaited_once_with()
        api.logout.assert_awaited_once_with()
        self.assertFalse(snapshots[-1].logged_in)
        self.assertEqual("", snapshots[-1].account_name)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)

    async def test_failed_logout_restores_persisted_kill_switch(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        unreachable = type("ProtonAPINotReachable", (Exception,), {})
        api.logout.side_effect = unreachable()
        api.is_user_logged_in.return_value = True
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "unreachable"):
            await adapter.logout()

        self.assertEqual(2, settings.killswitch)
        self.assertEqual(2, adapter._kill_switch)
        self.assertEqual(2, api.save_settings.await_count)
        self.assertTrue(adapter._logged_in)

    async def test_partially_successful_logout_publishes_signed_out_state(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        api.logout.side_effect = RuntimeError("late cleanup failed")
        api.is_user_logged_in.side_effect = [True, False]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "Signed out"):
            await adapter.logout()

        self.assertFalse(adapter._logged_in)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)
        self.assertEqual(0, adapter._kill_switch)
        self.assertEqual(1, api.save_settings.await_count)

    async def test_failed_logout_surfaces_kill_switch_rollback_failure(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 1
        api.logout.side_effect = RuntimeError("remote failure")
        api.save_settings.side_effect = [None, RuntimeError("disk failure")]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "could not be confirmed"):
            await adapter.logout()

        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)
        self.assertFalse(adapter._reconnector.enabled)
        self.assertEqual(0, adapter._kill_switch)
        self.assertEqual("protection_unknown", snapshots[-1].auth_state)

    async def test_cancelled_zero_save_finishes_before_compensation(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        first_save_started = asyncio.Event()
        release_first_save = asyncio.Event()
        compensation_started = asyncio.Event()
        persisted_kill_switch = 2
        save_calls = 0
        write_order = []

        async def delayed_executor_shaped_save(saved_settings):
            nonlocal persisted_kill_switch, save_calls
            save_calls += 1
            captured_kill_switch = saved_settings.killswitch
            if save_calls == 1:
                first_save_started.set()
                await release_first_save.wait()
            else:
                compensation_started.set()
            persisted_kill_switch = captured_kill_switch
            write_order.append(captured_kill_switch)

        api.save_settings.side_effect = delayed_executor_shaped_save
        api.is_user_logged_in.return_value = True
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        logout_task = asyncio.create_task(adapter.logout())
        await asyncio.wait_for(first_save_started.wait(), timeout=5)
        logout_task.cancel()
        await asyncio.sleep(0)
        self.assertFalse(compensation_started.is_set())
        release_first_save.set()
        with self.assertRaises(asyncio.CancelledError):
            await logout_task

        self.assertEqual(2, persisted_kill_switch)
        self.assertEqual(2, save_calls)
        self.assertEqual([0, 2], write_order)
        self.assertEqual(2, adapter._kill_switch)
        self.assertTrue(adapter._logged_in)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)

    async def test_unquiesced_zero_save_blocks_compensation_and_reconnection(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        first_save_started = asyncio.Event()
        release_first_save = asyncio.Event()
        first_save_finished = asyncio.Event()
        persisted_kill_switch = 2
        save_calls = 0

        async def blocked_executor_shaped_save(saved_settings):
            nonlocal persisted_kill_switch, save_calls
            save_calls += 1
            captured_kill_switch = saved_settings.killswitch
            first_save_started.set()
            await release_first_save.wait()
            persisted_kill_switch = captured_kill_switch
            first_save_finished.set()

        api.save_settings.side_effect = blocked_executor_shaped_save
        api.is_user_logged_in.return_value = True
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with patch(
            "proton_vpn_kde_backend.adapters.LOGOUT_RECOVERY_TIMEOUT_SECONDS",
            0.01,
        ):
            logout_task = asyncio.create_task(adapter.logout())
            await asyncio.wait_for(first_save_started.wait(), timeout=5)
            logout_task.cancel()
            try:
                await asyncio.sleep(0.03)
                self.assertFalse(logout_task.done())
                self.assertEqual(1, save_calls)
                self.assertFalse(first_save_finished.is_set())
            finally:
                release_first_save.set()
                with self.assertRaises(asyncio.CancelledError):
                    await logout_task

        self.assertEqual(1, save_calls)
        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)
        self.assertFalse(adapter._reconnector.enabled)
        self.assertEqual(0, snapshots[-1].kill_switch)
        self.assertEqual("protection_unknown", snapshots[-1].auth_state)

        self.assertTrue(first_save_finished.is_set())
        self.assertEqual(0, persisted_kill_switch)
        self.assertEqual(1, save_calls)
        self.assertEqual("protection_unknown", snapshots[-1].auth_state)

    async def test_late_zero_save_error_always_compensates(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        persisted_kill_switch = 2
        save_calls = 0

        async def commit_then_fail_once(saved_settings):
            nonlocal persisted_kill_switch, save_calls
            save_calls += 1
            persisted_kill_switch = saved_settings.killswitch
            if save_calls == 1:
                raise RuntimeError("late storage acknowledgement failure")

        api.save_settings.side_effect = commit_then_fail_once
        api.is_user_logged_in.return_value = True
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "could not complete"):
            await adapter.logout()

        self.assertEqual(2, persisted_kill_switch)
        self.assertEqual(2, save_calls)
        self.assertEqual(2, adapter._kill_switch)

    async def test_rollback_timeout_enters_protection_unknown_state(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        persisted_kill_switch = 2
        save_calls = 0
        rollback_started = asyncio.Event()
        release_rollback = asyncio.Event()

        async def block_rollback(saved_settings):
            nonlocal persisted_kill_switch, save_calls
            save_calls += 1
            if save_calls == 2:
                rollback_started.set()
                await release_rollback.wait()
            persisted_kill_switch = saved_settings.killswitch

        api.save_settings.side_effect = block_rollback
        api.logout.side_effect = RuntimeError("remote failure")
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with patch(
            "proton_vpn_kde_backend.adapters.LOGOUT_RECOVERY_TIMEOUT_SECONDS",
            0.01,
        ):
            logout_task = asyncio.create_task(adapter.logout())
            await asyncio.wait_for(rollback_started.wait(), timeout=5)
            try:
                await asyncio.sleep(0.03)
                self.assertFalse(logout_task.done())
                self.assertEqual(0, persisted_kill_switch)
                self.assertTrue(adapter._authentication_scope._lock.locked())
                self.assertTrue(adapter._connection_scope._lock.locked())
            finally:
                release_rollback.set()
                with self.assertRaisesRegex(RuntimeError, "could not be confirmed"):
                    await logout_task

        self.assertEqual(2, persisted_kill_switch)
        self.assertEqual(2, save_calls)
        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)
        self.assertFalse(adapter._reconnector.enabled)
        self.assertEqual(0, snapshots[-1].kill_switch)
        self.assertEqual("protection_unknown", snapshots[-1].auth_state)

    async def test_logout_rolls_back_when_reconnector_disable_fails(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        adapter._reconnector.disable = AsyncMock(
            side_effect=RuntimeError("reconnector failure")
        )

        with self.assertRaisesRegex(RuntimeError, "could not complete"):
            await adapter.logout()

        self.assertEqual(2, settings.killswitch)
        self.assertEqual(2, adapter._kill_switch)
        api.save_settings.assert_not_awaited()
        adapter._connector.disconnect.assert_not_awaited()
        api.logout.assert_not_awaited()
        self.assertTrue(adapter._logged_in)

    async def test_logout_waits_for_reconnect_worker_before_disconnect(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        release_connect = await self.start_cancellation_resistant_reconnect(
            adapter, connector
        )

        logout_task = asyncio.create_task(adapter.logout())
        try:
            for _ in range(20):
                if adapter._reconnector._retiring_retry_tasks:
                    break
                await asyncio.sleep(0)
            self.assertTrue(adapter._reconnector._retiring_retry_tasks)
            self.assertFalse(logout_task.done())
            connector.disconnect.assert_not_awaited()
            api.logout.assert_not_awaited()

            release_connect.set()
            await asyncio.wait_for(logout_task, timeout=1)
            # Compensation reaches Disconnected first; logout then issues one
            # idempotent Down to synchronize behind any late Core event.
            self.assertEqual(2, connector.disconnect.await_count)
            api.logout.assert_awaited_once_with()
        finally:
            release_connect.set()
            if not logout_task.done():
                await asyncio.wait_for(logout_task, timeout=1)

    async def test_disconnect_waits_for_reconnect_worker_before_returning(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        release_connect = await self.start_cancellation_resistant_reconnect(
            adapter, connector
        )

        async def disconnect():
            connector.current_state = state_named("Disconnected")

        connector.disconnect.side_effect = disconnect
        disconnect_task = asyncio.create_task(adapter.disconnect())
        try:
            for _ in range(20):
                if adapter._reconnector._retiring_retry_tasks:
                    break
                await asyncio.sleep(0)
            self.assertTrue(adapter._reconnector._retiring_retry_tasks)

            self.assertFalse(disconnect_task.done())
            connector.disconnect.assert_not_awaited()

            release_connect.set()
            await asyncio.wait_for(disconnect_task, timeout=1)
            self.assertEqual(2, connector.disconnect.await_count)
            self.assertIsNone(adapter._reconnector._retry_task)
            self.assertTrue(adapter._reconnector.enabled)
        finally:
            release_connect.set()
            if not disconnect_task.done():
                await asyncio.wait_for(disconnect_task, timeout=1)
            await adapter._reconnector.disable()

    async def test_logout_waits_for_an_accepted_public_disconnect(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        disconnect_started = asyncio.Event()
        release_disconnect = asyncio.Event()

        async def blocked_disconnect():
            disconnect_started.set()
            await release_disconnect.wait()
            connector.current_state = state_named("Disconnected")

        connector.current_state = state_named("Connected")
        connector.disconnect.side_effect = blocked_disconnect
        disconnect = asyncio.create_task(adapter.disconnect())
        await asyncio.wait_for(disconnect_started.wait(), timeout=5)
        logout = asyncio.create_task(adapter.logout())
        await asyncio.sleep(0)

        api.logout.assert_not_awaited()
        self.assertEqual(1, connector.disconnect.await_count)
        release_disconnect.set()
        await asyncio.wait_for(disconnect, timeout=1)
        await asyncio.wait_for(logout, timeout=1)

        # The accepted public disconnect and logout's stable-state barrier each
        # issue Down; the second call proves no queued Core event can overtake.
        self.assertEqual(2, connector.disconnect.await_count)
        api.logout.assert_awaited_once_with()

    async def test_overlapping_disconnects_do_not_share_reconnect_suspension(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        second_started = asyncio.Event()
        disconnect_count = 0

        async def disconnect():
            nonlocal disconnect_count
            disconnect_count += 1
            if disconnect_count == 1:
                first_started.set()
                await release_first.wait()
            else:
                second_started.set()
            connector.current_state = state_named("Disconnected")

        connector.disconnect.side_effect = disconnect
        first = asyncio.create_task(adapter.disconnect())
        await asyncio.wait_for(first_started.wait(), timeout=5)
        second = asyncio.create_task(adapter.disconnect())
        await asyncio.sleep(0)

        self.assertFalse(second_started.is_set())
        release_first.set()
        await first
        await asyncio.wait_for(second, timeout=1)

        self.assertTrue(second_started.is_set())
        self.assertEqual(2, connector.disconnect.await_count)
        self.assertIsNone(adapter._reconnector._retry_task)
        self.assertTrue(adapter._reconnector.enabled)
        await adapter._reconnector.disable()

    async def test_reentrant_locks_do_not_treat_child_tasks_as_the_owner(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        lock_contexts = (
            ("authentication", adapter._serialized_authentication_transition),
            ("connection", adapter._serialized_connection_lifecycle),
        )

        for lock_name, lock_context in lock_contexts:
            with self.subTest(lock=lock_name):
                child_entered = asyncio.Event()

                async def child(
                    context=lock_context, entered=child_entered
                ):
                    async with context():
                        entered.set()

                async with lock_context():
                    # Same-task nesting is the only supported re-entrant case.
                    async with lock_context():
                        pass
                    child_task = asyncio.create_task(child())
                    await asyncio.sleep(0)
                    entered_while_parent_owned = child_entered.is_set()

                await asyncio.wait_for(child_task, timeout=1.0)
                self.assertFalse(entered_while_parent_owned)
                self.assertTrue(child_entered.is_set())

    async def test_owned_authentication_delegate_does_not_authorize_siblings(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        delegate_entered = asyncio.Event()
        sibling_entered = asyncio.Event()

        async def reenter(entered: asyncio.Event):
            async with adapter._serialized_authentication_transition():
                entered.set()

        async with adapter._serialized_authentication_transition():
            delegate = adapter._create_owned_child_task(
                reenter(delegate_entered), authentication=True
            )
            sibling = asyncio.create_task(reenter(sibling_entered))
            await asyncio.wait_for(delegate, timeout=1.0)
            await asyncio.sleep(0)
            sibling_bypassed_owner = sibling_entered.is_set()

        await asyncio.wait_for(sibling, timeout=1.0)
        self.assertTrue(delegate_entered.is_set())
        self.assertFalse(sibling_bypassed_owner)
        self.assertTrue(sibling_entered.is_set())

    async def test_owned_connection_delegate_does_not_authorize_siblings(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        delegate_entered = asyncio.Event()
        sibling_entered = asyncio.Event()

        async def reenter(entered: asyncio.Event):
            async with adapter._serialized_connection_lifecycle():
                entered.set()

        async with adapter._serialized_connection_lifecycle():
            delegate = adapter._create_owned_child_task(
                reenter(delegate_entered), connection=True
            )
            sibling = asyncio.create_task(reenter(sibling_entered))
            await asyncio.wait_for(delegate, timeout=1.0)
            await asyncio.sleep(0)
            sibling_bypassed_owner = sibling_entered.is_set()

        await asyncio.wait_for(sibling, timeout=1.0)
        self.assertTrue(delegate_entered.is_set())
        self.assertFalse(sibling_bypassed_owner)
        self.assertTrue(sibling_entered.is_set())

    async def test_every_lifecycle_suspension_releases_when_lock_wait_is_cancelled(self):
        operation_factories = (
            ("disconnect", lambda adapter: adapter.disconnect()),
            ("logout", lambda adapter: adapter.logout()),
            (
                "reconnection preference",
                lambda adapter: adapter.set_reconnection_enabled(True),
            ),
            (
                "signed-out cleanup",
                lambda adapter: adapter._set_signed_out("Signed out"),
            ),
            (
                "session quiesce",
                lambda adapter: adapter._quiesce_session_services(),
            ),
            (
                "session expiry",
                lambda adapter: adapter._expire_session(
                    adapter._authentication_epoch
                ),
            ),
            ("close", lambda adapter: adapter.close()),
        )
        for operation_name, operation_factory in operation_factories:
            with self.subTest(operation=operation_name):
                api, _ = self.make_api()
                adapter = self.make_adapter(api)
                await adapter.initialize(Mock())
                connection_scope = adapter._serialized_connection_lifecycle()
                await connection_scope.__aenter__()
                operation = asyncio.create_task(operation_factory(adapter))
                for _ in range(20):
                    if adapter._reconnector._suspend_count:
                        break
                    await asyncio.sleep(0)
                self.assertEqual(1, adapter._reconnector._suspend_count)

                operation.cancel()
                if operation_name == "close":
                    # Close now retains its sole owner through caller
                    # cancellation. Release the conflicting scope before join.
                    await asyncio.sleep(0)
                    self.assertFalse(operation.done())
                    await connection_scope.__aexit__(None, None, None)
                result = (await asyncio.gather(
                    operation, return_exceptions=True
                ))[0]
                if operation_name != "close":
                    await connection_scope.__aexit__(None, None, None)

                if operation_name == "session quiesce":
                    self.assertTrue(result)
                else:
                    self.assertIsInstance(result, asyncio.CancelledError)
                self.assertEqual(0, adapter._reconnector._suspend_count)
                if adapter._reconnector.enabled:
                    await adapter._reconnector.disable()

    async def test_logout_settings_failure_releases_reconnection_suspension(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        api.load_settings.side_effect = RuntimeError("settings unavailable")

        with self.assertRaisesRegex(RuntimeError, "could not load"):
            await adapter.logout()

        self.assertEqual(0, adapter._reconnector._suspend_count)
        self.assertTrue(adapter._reconnector.enabled)
        await adapter._reconnector.disable()

    async def test_reconnection_enable_retry_does_not_leak_suspension(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        await adapter.set_reconnection_enabled(False)
        connector.register.side_effect = [RuntimeError("observer failure"), None]

        with self.assertRaisesRegex(RuntimeError, "observer failure"):
            await adapter.set_reconnection_enabled(True)
        self.assertEqual(0, adapter._reconnector._suspend_count)

        await adapter.set_reconnection_enabled(True)
        self.assertEqual(0, adapter._reconnector._suspend_count)
        self.assertTrue(adapter._reconnector.enabled)
        await adapter._reconnector.disable()

    async def test_repeated_retry_retirement_cannot_interrupt_compensating_down(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        connect_started = asyncio.Event()
        release_connect = asyncio.Event()
        compensation_started = asyncio.Event()
        release_compensation = asyncio.Event()
        compensation_cancelled = asyncio.Event()

        async def blocked_connect(*_args):
            connect_started.set()
            await release_connect.wait()

        async def compensating_disconnect():
            compensation_started.set()
            try:
                await release_compensation.wait()
            except asyncio.CancelledError:
                compensation_cancelled.set()
                raise
            connector.current_state = state_named("Disconnected")

        connector.connect.side_effect = blocked_connect
        connector.disconnect.side_effect = compensating_disconnect
        connector.current_connection = SimpleNamespace(
            server_id="server-id",
            server_name="",
            protocol="wireguard",
            backend="networkmanager",
        )
        api.refresher.server_list = SimpleNamespace(
            get_by_id=Mock(return_value="logical-server")
        )
        api.refresher.client_config = "client-config"
        adapter._reconnector._session_probe = SimpleNamespace(
            is_unlocked=AsyncMock(return_value=True),
            close=AsyncMock(),
        )
        connector.current_state = type(
            "Error",
            (),
            {"context": SimpleNamespace(
                event=type("UnexpectedError", (), {})()
            )},
        )()
        adapter._reconnector._delay_factory = lambda _attempt: 0
        adapter._reconnector.status_update(connector.current_state)
        await asyncio.wait_for(connect_started.wait(), timeout=5)

        first_entered = asyncio.Event()
        second_entered = asyncio.Event()
        release_owners = asyncio.Event()

        async def owner(entered: asyncio.Event):
            async with adapter._reconnector.suspended():
                entered.set()
                await release_owners.wait()

        first = asyncio.create_task(owner(first_entered))
        for _ in range(20):
            if adapter._reconnector._retiring_retry_tasks:
                break
            await asyncio.sleep(0)
        self.assertFalse(first_entered.is_set())
        release_connect.set()
        await asyncio.wait_for(compensation_started.wait(), timeout=5)
        second = asyncio.create_task(owner(second_entered))
        await asyncio.sleep(0)

        self.assertFalse(first_entered.is_set())
        self.assertFalse(second_entered.is_set())
        self.assertFalse(compensation_cancelled.is_set())
        self.assertEqual(1, connector.disconnect.await_count)

        release_compensation.set()
        await asyncio.wait_for(first_entered.wait(), timeout=5)
        await asyncio.wait_for(second_entered.wait(), timeout=5)
        release_owners.set()
        await asyncio.gather(first, second)

        self.assertFalse(compensation_cancelled.is_set())
        self.assertEqual(1, connector.disconnect.await_count)
        self.assertEqual(0, adapter._reconnector._suspend_count)
        self.assertEqual("Disconnected", type(connector.current_state).__name__)
        await adapter._reconnector.disable()

    async def test_close_drains_an_accepted_disconnect_scope(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        disconnect_started = asyncio.Event()
        release_disconnect = asyncio.Event()

        async def disconnect():
            disconnect_started.set()
            await release_disconnect.wait()
            connector.current_state = state_named("Disconnected")

        connector.disconnect.side_effect = disconnect
        disconnect_task = asyncio.create_task(adapter.disconnect())
        await asyncio.wait_for(disconnect_started.wait(), timeout=5)
        close_task = asyncio.create_task(adapter.close())
        await asyncio.sleep(0)

        self.assertFalse(close_task.done())
        connector.unregister.assert_not_called()
        release_disconnect.set()
        await asyncio.wait_for(disconnect_task, timeout=1)
        await asyncio.wait_for(close_task, timeout=1)
        connector.unregister.assert_any_call(adapter)

    async def test_logout_cannot_race_reconnector_reenable(self):
        api, _ = self.make_api()
        logout_started = asyncio.Event()
        release_logout = asyncio.Event()

        async def blocked_logout():
            logout_started.set()
            await release_logout.wait()

        api.logout.side_effect = blocked_logout
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        logout_task = asyncio.create_task(adapter.logout())
        await asyncio.wait_for(logout_started.wait(), timeout=5)

        preference_task = asyncio.create_task(
            adapter.set_reconnection_enabled(True)
        )
        await asyncio.sleep(0)
        self.assertFalse(preference_task.done())
        self.assertFalse(adapter._reconnector.enabled)
        release_logout.set()
        await logout_task
        await preference_task

        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._reconnector.enabled)

    async def test_cancelled_logout_restores_persistent_protection_state(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 2
        logout_started = asyncio.Event()
        release_logout = asyncio.Event()

        async def blocked_logout():
            logout_started.set()
            await release_logout.wait()

        api.logout.side_effect = blocked_logout
        api.is_user_logged_in.return_value = True
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        logout_task = asyncio.create_task(adapter.logout())
        await asyncio.wait_for(logout_started.wait(), timeout=5)
        logout_task.cancel()
        try:
            await asyncio.sleep(0)
            self.assertFalse(logout_task.done())
            self.assertEqual(1, api.save_settings.await_count)
            self.assertTrue(adapter._authentication_scope._lock.locked())
        finally:
            release_logout.set()
            with self.assertRaises(asyncio.CancelledError):
                await logout_task

        self.assertEqual(2, settings.killswitch)
        self.assertEqual(2, adapter._kill_switch)
        self.assertEqual(2, api.save_settings.await_count)
        self.assertTrue(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)

    async def test_core_state_probe_propagates_cancellation(self):
        api, _ = self.make_api(logged_in=False)
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with patch(
            "proton_vpn_kde_backend.adapters.run_in_daemon_thread",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await adapter._core_logged_in_after_failure()

    async def test_expired_api_session_returns_to_sign_in_state(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.refresher.get_up_to_date_server_list.side_effect = expired_error()
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await adapter.get_countries()

        self.assertFalse(snapshots[-1].logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)
        api.refresher.disable.assert_awaited_once_with()

    async def test_stale_session_error_cannot_sign_out_retired_account(self):
        api, _ = self.make_api()
        settings = api.load_settings.return_value
        stale_read_started = asyncio.Event()
        release_stale_read = asyncio.Event()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        load_count = 0

        async def load_settings():
            nonlocal load_count
            load_count += 1
            if load_count == 1:
                stale_read_started.set()
                await release_stale_read.wait()
                raise expired_error()
            return settings

        adapter = self.make_adapter(api)
        snapshots = []
        await adapter.initialize(snapshots.append)
        api.load_settings.side_effect = load_settings
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )

        stale_read = asyncio.create_task(adapter.get_settings())
        await asyncio.wait_for(stale_read_started.wait(), timeout=5)
        await adapter.logout()
        with self.assertRaisesRegex(RuntimeError, "restart the backend"):
            await adapter.login("replacement-user", "not-recorded")
        api.login.assert_not_awaited()
        cleanup_count = api.refresher.disable.await_count
        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)

        release_stale_read.set()
        with self.assertRaisesRegex(RuntimeError, "session changed"):
            await stale_read

        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)
        self.assertEqual(cleanup_count, api.refresher.disable.await_count)

    async def test_stale_server_error_cannot_sign_out_retired_account(self):
        api, _ = self.make_api()
        server_read_started = asyncio.Event()
        release_server_read = asyncio.Event()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})

        async def stale_server_list():
            server_read_started.set()
            await release_server_read.wait()
            raise expired_error()

        api.refresher.get_up_to_date_server_list.side_effect = stale_server_list
        adapter = self.make_adapter(api)
        snapshots = []
        await adapter.initialize(snapshots.append)
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )

        stale_read = asyncio.create_task(adapter.get_countries())
        await asyncio.wait_for(server_read_started.wait(), timeout=5)
        await adapter.logout()
        with self.assertRaisesRegex(RuntimeError, "restart the backend"):
            await adapter.login("replacement-user", "not-recorded")
        api.login.assert_not_awaited()
        cleanup_count = api.refresher.disable.await_count
        release_server_read.set()

        with self.assertRaisesRegex(RuntimeError, "session changed"):
            await stale_read
        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)
        self.assertEqual("account_restart_required", snapshots[-1].auth_state)
        self.assertEqual(cleanup_count, api.refresher.disable.await_count)

    async def test_stale_successful_search_cannot_poison_retired_cache(self):
        api, _ = self.make_api()
        stale_server_list = SimpleNamespace(logicals=[])
        stale_read_started = asyncio.Event()
        release_stale_read = asyncio.Event()

        async def delayed_server_list():
            stale_read_started.set()
            await release_stale_read.wait()
            return stale_server_list

        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        api.refresher.get_up_to_date_server_list.side_effect = delayed_server_list
        api.login.return_value = SimpleNamespace(
            authenticated=True,
            twofa_required=False,
        )

        stale_search = asyncio.create_task(adapter.search_locations("zurich"))
        await asyncio.wait_for(stale_read_started.wait(), timeout=5)
        await adapter.logout()
        with self.assertRaisesRegex(RuntimeError, "restart the backend"):
            await adapter.login("replacement-user", "not-recorded")
        api.login.assert_not_awaited()
        release_stale_read.set()

        with self.assertRaisesRegex(RuntimeError, "session changed"):
            await stale_search
        self.assertIsNone(adapter._search_projection)
        self.assertFalse(adapter._logged_in)

    async def test_login_waits_for_expiry_cleanup_then_requires_process_replacement(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.refresher.get_up_to_date_server_list.side_effect = expired_error()
        api.login.return_value = SimpleNamespace(
            success=True,
            authenticated=True,
            twofa_required=False,
        )
        adapter = self.make_adapter(api)
        snapshots = []
        await adapter.initialize(snapshots.append)
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        original_disable = adapter._reconnector.disable

        async def delayed_disable():
            cleanup_started.set()
            await release_cleanup.wait()
            await original_disable()

        adapter._reconnector.disable = AsyncMock(side_effect=delayed_disable)
        expiring_read = asyncio.create_task(adapter.get_countries())
        await asyncio.wait_for(cleanup_started.wait(), timeout=5)
        replacement_login = asyncio.create_task(
            adapter.login("replacement-user", "not-recorded")
        )
        await asyncio.sleep(0)

        api.login.assert_not_awaited()
        release_cleanup.set()
        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await expiring_read
        with self.assertRaisesRegex(RuntimeError, "restart the backend"):
            await asyncio.wait_for(replacement_login, timeout=1)
        api.login.assert_not_awaited()

        self.assertFalse(adapter._logged_in)
        self.assertFalse(adapter._session_services_enabled)
        self.assertEqual("expired", snapshots[-1].auth_state)

    async def test_expired_session_during_settings_save_stays_signed_out(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.save_settings.side_effect = expired_error()
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await adapter.update_settings({"moderateNat": True})

        self.assertEqual(1, api.save_settings.await_count)
        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)
        self.assertIn("sign in again", snapshots[-1].message)

    async def test_session_expiry_during_settings_compensation_stays_signed_out(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.save_settings.side_effect = [
            RuntimeError("late acknowledgement failure"),
            expired_error(),
        ]
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await adapter.update_settings({"moderateNat": True})

        self.assertEqual(2, api.save_settings.await_count)
        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)
        self.assertNotIn("restart", snapshots[-1].message)

    async def test_cancelled_settings_save_that_expires_stays_signed_out(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        save_started = asyncio.Event()
        release_save = asyncio.Event()

        async def delayed_expiry(_settings):
            save_started.set()
            await release_save.wait()
            raise expired_error()

        api.save_settings.side_effect = delayed_expiry
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with patch(
            "proton_vpn_kde_backend.adapters.LOGOUT_RECOVERY_TIMEOUT_SECONDS",
            0.01,
        ):
            update_task = asyncio.create_task(
                adapter.update_settings({"moderateNat": True})
            )
            await asyncio.wait_for(save_started.wait(), timeout=5)
            update_task.cancel()
            try:
                await asyncio.sleep(0.03)
                self.assertFalse(update_task.done())
            finally:
                release_save.set()
                with self.assertRaises(asyncio.CancelledError):
                    await update_task

        self.assertEqual(1, api.save_settings.await_count)
        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)

    async def test_expired_session_publishes_signed_out_when_cleanup_fails(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.refresher.get_up_to_date_server_list.side_effect = expired_error()
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)
        adapter._reconnector.disable = AsyncMock(
            side_effect=RuntimeError("observer cleanup failed")
        )
        api.refresher.disable.side_effect = RuntimeError("refresh cleanup failed")

        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await adapter.get_countries()

        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)
        self.assertIn("cleanup", snapshots[-1].message)

    async def test_expired_session_stays_signed_out_when_reconnector_cleanup_cancels(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.refresher.get_up_to_date_server_list.side_effect = expired_error()
        cleanup_started = asyncio.Event()

        async def blocked_cleanup():
            cleanup_started.set()
            await asyncio.Future()

        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)
        adapter._reconnector.disable = AsyncMock(side_effect=blocked_cleanup)

        request = asyncio.create_task(adapter.get_countries())
        await asyncio.wait_for(cleanup_started.wait(), timeout=5)
        request.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await request

        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)

    async def test_expired_session_stays_signed_out_when_refresher_cleanup_cancels(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.refresher.get_up_to_date_server_list.side_effect = expired_error()
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()

        async def blocked_cleanup():
            cleanup_started.set()
            await release_cleanup.wait()

        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)
        api.refresher.disable.side_effect = blocked_cleanup

        request = asyncio.create_task(adapter.get_countries())
        await asyncio.wait_for(cleanup_started.wait(), timeout=5)
        request.cancel()
        try:
            await asyncio.sleep(0)
            self.assertFalse(request.done())
            self.assertTrue(adapter._authentication_scope._lock.locked())
        finally:
            release_cleanup.set()
            with self.assertRaises(asyncio.CancelledError):
                await request

        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)

    async def test_disabled_reconnection_preference_survives_initialization(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)

        await adapter.set_reconnection_enabled(False)
        snapshot = await adapter.initialize(Mock())

        self.assertFalse(snapshot.reconnect_enabled)
        connector.register.assert_called_once_with(adapter)
        await adapter.close()
        connector.unregister.assert_called_once_with(adapter)

    async def test_state_mapping_exposes_only_safe_connection_metadata(self):
        from proton.vpn.session.servers import ServerFeatureEnum

        api, connector = self.make_api()
        connector.current_connection = SimpleNamespace(server_name="US-IL#42")
        logical_server = SimpleNamespace(
            location="Chicago, IL",
            exit_country="US",
            entry_country="CA",
            features=[ServerFeatureEnum.P2P, ServerFeatureEnum.TOR],
            smart_routing=True,
        )
        api.refresher.server_list = SimpleNamespace(
            get_by_name=Mock(return_value=logical_server)
        )
        adapter = self.make_adapter(api)
        adapter._connector = connector
        adapter._logged_in = True

        for state_name in (
            "Connected",
            "Connecting",
            "Disconnecting",
            "Disconnected",
            "Error",
        ):
            state = state_named(state_name)
            if state_name == "Connected":
                state.forwarded_port = 43123
            snapshot = adapter._snapshot_from_state(state)
            self.assertEqual(state_name.lower(), snapshot.state)
            self.assertEqual("US-IL#42", snapshot.server_name)

        self.assertEqual("Chicago, IL", snapshot.server_location)
        connected = state_named("Connected")
        connected.forwarded_port = 43123
        snapshot = adapter._snapshot_from_state(connected)
        self.assertEqual(43123, snapshot.forwarded_port)
        self.assertEqual("US", snapshot.exit_country)
        self.assertEqual("CA", snapshot.entry_country)
        self.assertTrue(snapshot.tor)
        self.assertTrue(snapshot.p2p)
        self.assertTrue(snapshot.smart_routing)

        self.assertEqual(
            "error", adapter._snapshot_from_state(state_named("FutureState")).state
        )

        error_codes = {
            "TunnelSetupFailed": "tunnel_setup_failed",
            "AuthDenied": "authentication_denied",
            "Timeout": "timeout",
            "DeviceDisconnected": "device_disconnected",
            "MaximumSessionsReached": "maximum_sessions_reached",
            "ExpiredCertificate": "certificate_expired",
            "NotYetValidCertificate": "certificate_not_yet_valid",
            "TwoFARequired": "two_factor_required",
            "UnexpectedError": "unexpected_error",
            "FutureError": "unexpected_error",
        }
        for event_name, expected_code in error_codes.items():
            with self.subTest(event_name=event_name):
                error_state = state_named("Error")
                error_state.context = SimpleNamespace(event=state_named(event_name))
                self.assertEqual(
                    expected_code,
                    adapter._snapshot_from_state(error_state).error_code,
                )

    async def test_connect_fastest_uses_official_selection_and_saved_protocol(self):
        api, connector = self.make_api()
        logical_server = object()
        server_list = SimpleNamespace(get_fastest=Mock(return_value=logical_server))
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = self.make_adapter(api)
        adapter._connector = connector
        adapter._logged_in = True

        await adapter.connect_fastest()

        server_list.get_fastest.assert_called_once_with()
        connector.get_vpn_server.assert_called_once_with(
            logical_server, "client-config"
        )
        connector.connect.assert_awaited_once_with("vpn-server", protocol="wireguard")

    async def test_expiry_during_connect_stops_before_connector_side_effect(self):
        api, connector = self.make_api()
        logical_server = object()
        api.refresher.get_up_to_date_server_list.return_value = SimpleNamespace(
            get_fastest=Mock(return_value=logical_server)
        )
        config_started = asyncio.Event()
        release_config = asyncio.Event()

        async def delayed_client_config():
            config_started.set()
            await release_config.wait()
            return "client-config"

        api.refresher.get_up_to_date_client_config.side_effect = (
            delayed_client_config
        )
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        connect = asyncio.create_task(adapter.connect_fastest())
        await asyncio.wait_for(config_started.wait(), timeout=5)

        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        api.load_settings.side_effect = expired_error()
        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await adapter.get_settings()
        release_config.set()

        with self.assertRaises(asyncio.CancelledError):
            await connect
        connector.get_vpn_server.assert_not_called()
        connector.connect.assert_not_awaited()

    async def test_disconnect_retires_every_manual_route_during_target_lookup(self):
        """Disconnect joins every public manual route without external release."""
        routes = (
            ("fastest", lambda adapter: adapter.connect_fastest()),
            (
                "fastest-features",
                lambda adapter: adapter.connect_fastest_with_features(("p2p",)),
            ),
            ("country", lambda adapter: adapter.connect_country("CH")),
            (
                "country-features",
                lambda adapter: adapter.connect_country_with_features(
                    "CH", ("p2p",)
                ),
            ),
            (
                "group",
                lambda adapter: adapter.connect_group(
                    "CH", "location", "Zurich"
                ),
            ),
            (
                "group-features",
                lambda adapter: adapter.connect_group_with_features(
                    "CH", "location", "Zurich", ("p2p",)
                ),
            ),
            ("server", lambda adapter: adapter.connect_server("CH#10")),
        )

        for route_name, connect_route in routes:
            with self.subTest(route=route_name):
                api, connector = self.make_api()
                logical_server = object()
                server_list = SimpleNamespace(
                    logicals=[logical_server],
                    user_tier=2,
                    get_fastest=Mock(return_value=logical_server),
                    get_fastest_in_country=Mock(return_value=logical_server),
                    get_by_name=Mock(return_value=logical_server),
                    get_available_servers=Mock(return_value=[logical_server]),
                    get_fastest_server=Mock(return_value=logical_server),
                )
                lookup_started = asyncio.Event()
                release_lookup = asyncio.Event()

                async def delayed_server_list(
                    started=lookup_started,
                    release=release_lookup,
                    result=server_list,
                ):
                    started.set()
                    await release.wait()
                    return result

                adapter = self.make_adapter(api)
                await adapter.initialize(Mock())
                adapter._country = Mock(
                    return_value=SimpleNamespace(servers=[logical_server])
                )
                adapter._server_group = Mock(
                    return_value=SimpleNamespace(servers=[logical_server])
                )
                adapter._fastest_matching = Mock(return_value=logical_server)
                api.refresher.get_up_to_date_server_list.side_effect = (
                    delayed_server_list
                )

                connection = asyncio.create_task(connect_route(adapter))
                await asyncio.wait_for(lookup_started.wait(), timeout=5)
                try:
                    await adapter.disconnect()
                    with self.assertRaises(asyncio.CancelledError):
                        await connection
                finally:
                    release_lookup.set()
                    if not connection.done():
                        connection.cancel()
                    try:
                        await connection
                    except asyncio.CancelledError:
                        pass

                connector.get_vpn_server.assert_not_called()
                connector.connect.assert_not_awaited()
                self.assertFalse(adapter._manual_connection_tasks)
                self.assertEqual(0, adapter._reconnector._suspend_count)

    async def test_all_terminal_transitions_retire_a_manual_target(self):
        """All invalidators use the same cancellation-and-join boundary."""
        transitions = (
            ("disconnect", lambda adapter: adapter.disconnect()),
            ("logout", lambda adapter: adapter.logout()),
            ("close", lambda adapter: adapter.close()),
            (
                "disable-reconnection",
                lambda adapter: adapter.set_reconnection_enabled(False),
            ),
            (
                "session-expiry",
                lambda adapter: adapter._expire_session(
                    adapter._authentication_epoch
                ),
            ),
        )

        for transition_name, transition in transitions:
            with self.subTest(transition=transition_name):
                api, connector = self.make_api()
                lookup_started = asyncio.Event()

                async def blocked_server_list(started=lookup_started):
                    started.set()
                    await asyncio.Future()

                api.refresher.get_up_to_date_server_list.side_effect = (
                    blocked_server_list
                )
                adapter = self.make_adapter(api)
                await adapter.initialize(Mock())
                connection = asyncio.create_task(adapter.connect_fastest())
                await asyncio.wait_for(lookup_started.wait(), timeout=5)

                await transition(adapter)

                with self.assertRaises(asyncio.CancelledError):
                    await connection
                connector.get_vpn_server.assert_not_called()
                connector.connect.assert_not_awaited()
                self.assertFalse(adapter._manual_connection_tasks)
                self.assertEqual(0, adapter._reconnector._suspend_count)

    async def test_controller_disconnect_retires_lookup_and_clears_busy(self):
        api, _ = self.make_api()
        lookup_started = asyncio.Event()

        async def blocked_server_list():
            lookup_started.set()
            await asyncio.Future()

        api.refresher.get_up_to_date_server_list.side_effect = blocked_server_list
        adapter = self.make_adapter(api)
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())

        connection = asyncio.create_task(controller.connect_fastest())
        await asyncio.wait_for(lookup_started.wait(), timeout=5)
        self.assertTrue(controller.snapshot.busy)

        await controller.disconnect()

        with self.assertRaises(asyncio.CancelledError):
            await connection
        self.assertFalse(controller.snapshot.busy)
        self.assertFalse(adapter._manual_connection_tasks)
        self.assertEqual(0, adapter._reconnector._suspend_count)

    async def test_all_invalidators_drain_a_queued_core_replacement(self):
        """Core 5.6.10 Down-in-Disconnecting cannot survive invalidation."""
        transitions = (
            ("disconnect", lambda adapter: adapter.disconnect()),
            ("logout", lambda adapter: adapter.logout()),
            ("close", lambda adapter: adapter.close()),
            (
                "disable-reconnection",
                lambda adapter: adapter.set_reconnection_enabled(False),
            ),
            (
                "signed-out-cleanup",
                lambda adapter: adapter._set_signed_out("Signed out"),
            ),
            (
                "session-expiry",
                lambda adapter: adapter._expire_session(
                    adapter._authentication_epoch
                ),
            ),
        )

        for transition_name, transition in transitions:
            with self.subTest(transition=transition_name):
                api, connector = self.make_api()
                terminal_exit = Mock(
                    side_effect=RuntimeError("unexpected terminal exit")
                )
                adapter = self.make_adapter(api, terminal_exit=terminal_exit)
                await adapter.initialize(Mock())
                connector.current_state = state_named("Disconnecting")
                first_down = asyncio.Event()
                replacement_down = asyncio.Event()
                ignored_replacement_down = asyncio.Event()
                disconnect_count = 0

                async def disconnect(
                    first_down=first_down,
                    replacement_down=replacement_down,
                    ignored_replacement_down=ignored_replacement_down,
                    connector=connector,
                    adapter=adapter,
                ):
                    nonlocal disconnect_count
                    disconnect_count += 1
                    if disconnect_count == 1:
                        # Core 5.6.10 ignores Down while its old connection is
                        # Disconnecting and retains the queued replacement.
                        first_down.set()
                    elif disconnect_count == 2:
                        replacement_down.set()
                        connector.current_state = state_named("Disconnecting")
                        adapter.status_update(connector.current_state)
                    elif disconnect_count == 3:
                        ignored_replacement_down.set()
                    elif disconnect_count == 4:
                        self.assertEqual("Disconnected", type(connector.current_state).__name__)
                    else:
                        self.fail("Stable disconnect issued an unexpected Down")

                connector.disconnect.side_effect = disconnect
                invalidator = asyncio.create_task(transition(adapter))
                await asyncio.wait_for(first_down.wait(), timeout=1)
                self.assertFalse(invalidator.done())

                # The old connection's late Disconnected event immediately
                # promotes the queued target to Connecting inside Core's lock.
                connector.current_state = state_named("Connecting")
                adapter.status_update(connector.current_state)
                await asyncio.wait_for(replacement_down.wait(), timeout=1)
                await asyncio.wait_for(
                    ignored_replacement_down.wait(), timeout=1
                )
                self.assertFalse(invalidator.done())

                connector.current_state = state_named("Disconnected")
                adapter.status_update(connector.current_state)
                await asyncio.wait_for(invalidator, timeout=1)

                self.assertEqual(4, connector.disconnect.await_count)
                self.assertEqual(
                    "Disconnected", type(connector.current_state).__name__
                )
                self.assertEqual(0, adapter._reconnector._suspend_count)
                terminal_exit.assert_not_called()

    async def test_unconfirmed_foreground_operation_uses_process_retirement(self):
        api, _ = self.make_api()
        terminal_exit = Mock(side_effect=RuntimeError("recorded terminal exit"))
        adapter = self.make_adapter(api, terminal_exit=terminal_exit)

        with self.assertRaisesRegex(RuntimeError, "recorded terminal exit"):
            adapter.retire_unconfirmed_operation()

        terminal_exit.assert_called_once_with(1)
        api.logout.assert_not_awaited()

    async def test_failed_stable_disconnect_forces_fresh_backend(self):
        api, connector = self.make_api()
        terminal_exit = Mock(side_effect=RuntimeError("forced backend exit"))
        adapter = self.make_adapter(api, terminal_exit=terminal_exit)
        await adapter.initialize(Mock())
        connector.current_state = state_named("Connecting")
        connector.disconnect.side_effect = RuntimeError("Down failed")

        with self.assertLogs(
            "proton_vpn_kde_backend.adapters", level="CRITICAL"
        ):
            with self.assertRaisesRegex(RuntimeError, "forced backend exit"):
                await adapter.disconnect()

        terminal_exit.assert_called_once_with(1)

    async def test_failed_cancel_compensation_forces_fresh_backend(self):
        api, connector = self.make_api()
        operation_started = asyncio.Event()
        release_operation = asyncio.Event()
        terminal_exit = Mock(side_effect=RuntimeError("forced backend exit"))
        adapter = self.make_adapter(api, terminal_exit=terminal_exit)
        await adapter.initialize(Mock())

        async def operation():
            operation_started.set()
            await release_operation.wait()

        connector.current_state = state_named("Connecting")
        connector.disconnect.side_effect = RuntimeError("compensation failed")
        attempt = asyncio.create_task(
            adapter._attempt_connection(
                operation,
                adapter._authentication_epoch,
                adapter._connection_intent_generation,
            )
        )
        await asyncio.wait_for(operation_started.wait(), timeout=5)
        attempt.cancel()
        release_operation.set()

        with self.assertLogs(
            "proton_vpn_kde_backend.adapters", level="CRITICAL"
        ):
            with self.assertRaisesRegex(RuntimeError, "forced backend exit"):
                await attempt

        terminal_exit.assert_called_once_with(1)

    async def test_cancellation_resistant_lookup_forces_fresh_backend(self):
        api, _ = self.make_api()
        lookup_started = asyncio.Event()
        release_lookup = asyncio.Event()
        terminal_exit = Mock()

        async def cancellation_resistant_lookup():
            lookup_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                await release_lookup.wait()
            return SimpleNamespace(get_fastest=Mock(return_value=object()))

        api.refresher.get_up_to_date_server_list.side_effect = (
            cancellation_resistant_lookup
        )
        adapter = ProtonCoreAdapter(
            api,
            connection_retirement_seconds=0.01,
            terminal_exit=terminal_exit,
        )
        await adapter.initialize(Mock())
        connection = asyncio.create_task(adapter.connect_fastest())
        await asyncio.wait_for(lookup_started.wait(), timeout=5)

        try:
            with self.assertLogs(
                "proton_vpn_kde_backend.adapters", level="CRITICAL"
            ):
                with self.assertRaises(SystemExit) as exit_context:
                    await adapter.disconnect()
            self.assertEqual(1, exit_context.exception.code)
            terminal_exit.assert_called_once_with(1)
        finally:
            release_lookup.set()
            await connection

        self.assertFalse(adapter._manual_connection_tasks)
        self.assertEqual(0, adapter._reconnector._suspend_count)

    async def test_cancellation_resistant_retry_forces_fresh_backend(self):
        api, connector = self.make_api()
        retry_started = asyncio.Event()
        release_retry = asyncio.Event()
        terminal_exit = Mock()

        async def cancellation_resistant_connect(*_args):
            retry_started.set()
            await release_retry.wait()

        connector.connect.side_effect = cancellation_resistant_connect
        adapter = ProtonCoreAdapter(
            api,
            connection_retirement_seconds=0.01,
            terminal_exit=terminal_exit,
        )
        await adapter.initialize(Mock())

        async def disconnect():
            connector.current_state = state_named("Disconnected")
            adapter.status_update(connector.current_state)

        connector.disconnect.side_effect = disconnect
        connector.current_connection = SimpleNamespace(
            server_id="server-id",
            server_name="",
            protocol="wireguard",
            backend="networkmanager",
        )
        api.refresher.server_list = SimpleNamespace(
            get_by_id=Mock(return_value="logical-server")
        )
        api.refresher.client_config = "client-config"
        adapter._reconnector._session_probe = SimpleNamespace(
            is_unlocked=AsyncMock(return_value=True),
            close=AsyncMock(),
        )
        connector.current_state = type(
            "Error",
            (),
            {"context": SimpleNamespace(
                event=type("UnexpectedError", (), {})()
            )},
        )()
        adapter._reconnector._delay_factory = lambda _attempt: 0
        adapter._reconnector.status_update(connector.current_state)
        await asyncio.wait_for(retry_started.wait(), timeout=5)
        retry_task = adapter._reconnector._retry_task
        self.assertIsNotNone(retry_task)

        try:
            with self.assertLogs(
                "proton_vpn_kde_backend.adapters", level="CRITICAL"
            ):
                with self.assertRaises(SystemExit) as exit_context:
                    await adapter.disconnect()
            self.assertEqual(1, exit_context.exception.code)
            terminal_exit.assert_called_once_with(1)
        finally:
            release_retry.set()
            assert retry_task is not None
            try:
                await retry_task
            except asyncio.CancelledError:
                pass

        self.assertEqual(0, adapter._reconnector._suspend_count)

    async def test_every_manual_route_owns_each_automatic_retry_preflight(self):
        """Manual intent retires retries before lookup and blocks replacements."""
        routes = (
            ("fastest", lambda adapter: adapter.connect_fastest()),
            (
                "fastest-features",
                lambda adapter: adapter.connect_fastest_with_features(("p2p",)),
            ),
            ("country", lambda adapter: adapter.connect_country("CH")),
            (
                "country-features",
                lambda adapter: adapter.connect_country_with_features(
                    "CH", ("p2p",)
                ),
            ),
            (
                "group",
                lambda adapter: adapter.connect_group(
                    "CH", "location", "Zurich"
                ),
            ),
            (
                "group-features",
                lambda adapter: adapter.connect_group_with_features(
                    "CH", "location", "Zurich", ("p2p",)
                ),
            ),
            ("server", lambda adapter: adapter.connect_server("CH#10")),
        )

        for phase in ("delay", "network", "session"):
            for route_name, connect_route in routes:
                with self.subTest(phase=phase, route=route_name):
                    api, connector = self.make_api()
                    logical_server = object()
                    server_list = SimpleNamespace(
                        logicals=[logical_server],
                        user_tier=2,
                        get_fastest=Mock(return_value=logical_server),
                        get_fastest_in_country=Mock(return_value=logical_server),
                        get_by_name=Mock(return_value=logical_server),
                        get_by_id=Mock(return_value=logical_server),
                        get_available_servers=Mock(return_value=[logical_server]),
                        get_fastest_server=Mock(return_value=logical_server),
                    )
                    lookup_started = asyncio.Event()
                    release_lookup = asyncio.Event()
                    preflight_started = asyncio.Event()
                    preflight_cancelled = asyncio.Event()
                    release_preflight = asyncio.Event()

                    async def delayed_server_list(
                        started=lookup_started,
                        release=release_lookup,
                        result=server_list,
                    ):
                        started.set()
                        await release.wait()
                        return result

                    async def blocking_preflight(
                        started=preflight_started,
                        cancelled=preflight_cancelled,
                        release=release_preflight,
                    ):
                        started.set()
                        try:
                            await asyncio.Future()
                        except asyncio.CancelledError:
                            cancelled.set()
                            await release.wait()
                        return True

                    async def connect(*_args, target=connector, **_kwargs):
                        target.current_state = state_named("Connected")

                    adapter = self.make_adapter(api)
                    await adapter.initialize(Mock())
                    adapter._country = Mock(
                        return_value=SimpleNamespace(servers=[logical_server])
                    )
                    adapter._server_group = Mock(
                        return_value=SimpleNamespace(servers=[logical_server])
                    )
                    adapter._fastest_matching = Mock(return_value=logical_server)
                    api.refresher.get_up_to_date_server_list.side_effect = (
                        delayed_server_list
                    )
                    api.refresher.server_list = server_list
                    api.refresher.client_config = "client-config"
                    connector.connect.side_effect = connect
                    connector.current_connection = SimpleNamespace(
                        server_id="server-id",
                        server_name="",
                        protocol="wireguard",
                        backend="networkmanager",
                    )
                    connector.current_state = state_named("Error")

                    reconnector = adapter._reconnector
                    self.assertIsNotNone(reconnector)
                    reconnector._delay_factory = (
                        (lambda _attempt: 3600)
                        if phase == "delay"
                        else (lambda _attempt: 0)
                    )
                    if phase == "network":
                        reconnector._network_probe = blocking_preflight
                    else:
                        reconnector._network_probe = AsyncMock(return_value=True)
                    if phase == "session":
                        reconnector._session_probe = SimpleNamespace(
                            is_unlocked=blocking_preflight,
                            close=AsyncMock(),
                        )
                    else:
                        reconnector._session_probe = SimpleNamespace(
                            is_unlocked=AsyncMock(return_value=True),
                            close=AsyncMock(),
                        )

                    reconnector.status_update(connector.current_state)
                    if phase == "delay":
                        await asyncio.sleep(0)
                    else:
                        await asyncio.wait_for(preflight_started.wait(), timeout=5)

                    manual = asyncio.create_task(connect_route(adapter))
                    try:
                        if phase != "delay":
                            await asyncio.wait_for(preflight_cancelled.wait(), timeout=5)
                            self.assertFalse(lookup_started.is_set())
                            self.assertEqual(0, connector.connect.await_count)
                            release_preflight.set()

                        await asyncio.wait_for(lookup_started.wait(), timeout=5)
                        reconnector.status_update(connector.current_state)
                        self.assertIsNone(reconnector._retry_task)
                        self.assertEqual(0, connector.connect.await_count)

                        release_lookup.set()
                        await asyncio.wait_for(manual, timeout=1.0)
                        self.assertEqual(1, connector.connect.await_count)
                    finally:
                        release_preflight.set()
                        release_lookup.set()
                        if not manual.done():
                            manual.cancel()
                        try:
                            await manual
                        except asyncio.CancelledError:
                            pass
                        await adapter.close()

    async def test_newer_manual_target_retires_an_older_target_lookup(self):
        api, connector = self.make_api()
        older_server = object()
        newer_server = object()
        server_list = SimpleNamespace(
            get_fastest=Mock(return_value=older_server),
            get_by_name=Mock(return_value=newer_server),
        )
        older_lookup_started = asyncio.Event()
        release_older_lookup = asyncio.Event()
        lookup_count = 0

        async def server_lookup():
            nonlocal lookup_count
            lookup_count += 1
            if lookup_count == 1:
                older_lookup_started.set()
                await release_older_lookup.wait()
            return server_list

        api.refresher.get_up_to_date_server_list.side_effect = server_lookup
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        older = asyncio.create_task(adapter.connect_fastest())
        await asyncio.wait_for(older_lookup_started.wait(), timeout=5)
        newer = asyncio.create_task(adapter.connect_server("CH#10"))
        await asyncio.wait_for(newer, timeout=1.0)

        with self.assertRaises(asyncio.CancelledError):
            await older

        connector.get_vpn_server.assert_called_once_with(
            newer_server, "client-config"
        )
        connector.connect.assert_awaited_once_with(
            "vpn-server", protocol="wireguard"
        )
        self.assertFalse(adapter._manual_connection_tasks)
        self.assertEqual(0, adapter._reconnector._suspend_count)
        await adapter.close()

    async def test_unknown_refresher_cleanup_is_normalized_before_reenable(self):
        api, connector = self.make_api(logged_in=False)
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        adapter._logged_in = True
        events: list[str] = []

        async def ambiguous_enable():
            events.append("enable-ambiguous")
            raise RuntimeError("enable acknowledgement lost")

        async def ambiguous_disable():
            events.append("disable-ambiguous")
            raise RuntimeError("disable acknowledgement lost")

        api.refresher.enable.side_effect = ambiguous_enable
        api.refresher.disable.side_effect = ambiguous_disable
        with self.assertRaisesRegex(RuntimeError, "enable acknowledgement"):
            await adapter._enable_session_services()

        self.assertFalse(adapter._session_services_enabled)
        self.assertEqual("CLEANUP_REQUIRED", adapter._session_services_state.name)

        async def confirmed_disable():
            events.append("disable-confirmed")

        async def confirmed_enable():
            events.append("enable-confirmed")

        api.refresher.disable.side_effect = confirmed_disable
        api.refresher.enable.side_effect = confirmed_enable
        await adapter._enable_session_services()

        self.assertEqual(
            [
                "enable-ambiguous",
                "disable-ambiguous",
                "disable-confirmed",
                "enable-confirmed",
            ],
            events,
        )
        self.assertTrue(adapter._session_services_enabled)
        connector.connect.assert_not_awaited()

    async def test_close_retries_completion_unknown_refresher_disable(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        api.refresher.disable.side_effect = RuntimeError(
            "disable acknowledgement lost"
        )
        with self.assertRaisesRegex(RuntimeError, "acknowledgement lost"):
            await adapter._disable_refresher()
        self.assertEqual("CLEANUP_REQUIRED", adapter._session_services_state.name)

        api.refresher.disable.side_effect = None
        await adapter.close()

        self.assertEqual(2, api.refresher.disable.await_count)
        self.assertEqual("DISABLED", adapter._session_services_state.name)
        connector.unregister.assert_any_call(adapter)

    async def test_retry_owner_rechecks_intent_and_account_after_scope_wait(self):
        for invalidator in ("account", "intent"):
            with self.subTest(invalidator=invalidator):
                api, connector = self.make_api()
                adapter = self.make_adapter(api)
                await adapter.initialize(Mock())
                self.assertEqual(
                    adapter._attempt_reconnection,
                    adapter._reconnector._connection_attempt,
                )
                epoch = adapter._authentication_epoch
                entered = asyncio.Event()

                async def request_retry(adapter=adapter, entered=entered, epoch=epoch):
                    entered.set()
                    return await adapter._attempt_reconnection(
                        "vpn-server", "wireguard", "networkmanager", epoch
                    )

                retry = None
                try:
                    async with adapter._serialized_connection_lifecycle():
                        retry = asyncio.create_task(request_retry())
                        await asyncio.wait_for(entered.wait(), timeout=1)
                        self.assertFalse(retry.done())
                        connector.connect.assert_not_awaited()
                        if invalidator == "account":
                            adapter._authentication_epoch += 1
                        else:
                            adapter._advance_connection_intent()
                    if invalidator == "account":
                        with self.assertRaisesRegex(RuntimeError, "session changed"):
                            await asyncio.wait_for(retry, timeout=1)
                    else:
                        self.assertFalse(await asyncio.wait_for(retry, timeout=1))
                    connector.connect.assert_not_awaited()
                    connector.disconnect.assert_not_awaited()
                finally:
                    if retry is not None:
                        if not retry.done():
                            retry.cancel()
                        await asyncio.gather(retry, return_exceptions=True)
                    await adapter._reconnector.disable()

    async def test_retry_owner_compensates_stale_success(self):
        for invalidator in ("account", "intent"):
            with self.subTest(invalidator=invalidator):
                api, connector = self.make_api()
                adapter = self.make_adapter(api)
                await adapter.initialize(Mock())
                epoch = adapter._authentication_epoch

                async def connect(
                    *_args, adapter=adapter, connector=connector, invalidator=invalidator
                ):
                    connector.current_state = state_named("Connected")
                    if invalidator == "account":
                        adapter._authentication_epoch += 1
                    else:
                        adapter._advance_connection_intent()

                connector.connect.side_effect = connect
                try:
                    if invalidator == "account":
                        with self.assertRaisesRegex(RuntimeError, "session changed"):
                            await adapter._attempt_reconnection(
                                "vpn-server", "wireguard", "networkmanager", epoch
                            )
                    else:
                        self.assertFalse(await adapter._attempt_reconnection(
                            "vpn-server", "wireguard", "networkmanager", epoch
                        ))
                    connector.connect.assert_awaited_once_with(
                        "vpn-server", "wireguard", "networkmanager"
                    )
                    connector.disconnect.assert_awaited_once_with()
                    self.assertEqual("Disconnected", type(connector.current_state).__name__)
                finally:
                    await adapter._reconnector.disable()

    async def test_manual_connect_retires_and_joins_automatic_attempt(self):
        api, connector = self.make_api()
        logical_server = object()
        server_list = SimpleNamespace(
            get_fastest=Mock(return_value=logical_server),
            get_by_id=Mock(return_value=logical_server),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        api.refresher.server_list = server_list
        api.refresher.client_config = "client-config"
        auto_started = asyncio.Event()
        release_auto = threading.Event()
        manual_lookup_started = asyncio.Event()
        active_calls = 0
        maximum_active_calls = 0
        connect_calls = 0

        async def connect(*_args, **_kwargs):
            nonlocal active_calls, maximum_active_calls, connect_calls
            connect_calls += 1
            active_calls += 1
            maximum_active_calls = max(maximum_active_calls, active_calls)
            try:
                if connect_calls == 1:
                    auto_started.set()
                    # Core 5.6.10's LinuxNetworkManager.start() has this
                    # ownership shape: an asyncio coroutine waits for a
                    # NetworkManager future in the default executor.
                    await asyncio.get_running_loop().run_in_executor(
                        None, release_auto.wait
                    )
                connector.current_state = state_named("Connected")
            finally:
                active_calls -= 1

        async def disconnect():
            connector.current_state = state_named("Disconnected")

        connector.connect.side_effect = connect
        connector.disconnect.side_effect = disconnect

        async def current_server_list():
            manual_lookup_started.set()
            return server_list

        api.refresher.get_up_to_date_server_list.side_effect = current_server_list
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        connector.current_connection = SimpleNamespace(
            server_id="server-id",
            server_name="",
            protocol="wireguard",
            backend="networkmanager",
        )
        connector.current_state = state_named("Error")
        adapter._reconnector._delay_factory = lambda _attempt: 0
        adapter._reconnector._session_probe = SimpleNamespace(
            is_unlocked=AsyncMock(return_value=True),
            close=AsyncMock(),
        )
        adapter._reconnector.status_update(connector.current_state)
        await asyncio.wait_for(auto_started.wait(), timeout=5)

        manual = asyncio.create_task(adapter.connect_fastest())
        try:
            for _ in range(20):
                if adapter._reconnector._retiring_retry_tasks:
                    break
                await asyncio.sleep(0)
            self.assertTrue(adapter._reconnector._retiring_retry_tasks)
            self.assertFalse(manual.done())
            self.assertFalse(manual_lookup_started.is_set())
            self.assertEqual(1, maximum_active_calls)

            release_auto.set()
            await asyncio.wait_for(manual, timeout=1)

            self.assertEqual(2, connect_calls)
            self.assertEqual(1, maximum_active_calls)
            connector.disconnect.assert_awaited_once_with()
            self.assertEqual("Connected", type(connector.current_state).__name__)
        finally:
            release_auto.set()
            if not manual.done():
                manual.cancel()
                try:
                    await manual
                except asyncio.CancelledError:
                    pass

    async def test_expiry_after_connect_success_compensates_stale_tunnel(self):
        api, connector = self.make_api()
        logical_server = object()
        api.refresher.get_up_to_date_server_list.return_value = SimpleNamespace(
            get_fastest=Mock(return_value=logical_server)
        )
        settings = api.load_settings.return_value
        connect_started = asyncio.Event()
        release_connect = asyncio.Event()

        async def delayed_connect(*_args, **_kwargs):
            connect_started.set()
            await release_connect.wait()
            connector.current_state = state_named("Connected")

        async def disconnect():
            connector.current_state = state_named("Disconnected")

        connector.connect.side_effect = delayed_connect
        connector.disconnect.side_effect = disconnect
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        api.load_settings.side_effect = [
            settings,
            type("ProtonAPIAuthenticationNeeded", (Exception,), {})(),
        ]

        connect = asyncio.create_task(adapter.connect_fastest())
        await asyncio.wait_for(connect_started.wait(), timeout=5)
        expiry = asyncio.create_task(adapter.get_settings())
        for _ in range(20):
            if not adapter._logged_in:
                break
            await asyncio.sleep(0)
        self.assertFalse(adapter._logged_in)

        release_connect.set()
        with self.assertRaises(asyncio.CancelledError):
            await connect
        with self.assertRaisesRegex(RuntimeError, "session expired"):
            await expiry

        # Compensation plus the expiry path's public event barrier.
        self.assertEqual(2, connector.disconnect.await_count)
        self.assertEqual("Disconnected", type(connector.current_state).__name__)
        self.assertFalse(adapter._logged_in)

    async def test_capability_intersection_uses_official_filter_and_score(self):
        from proton.vpn.session.servers import ServerFeatureEnum

        api, connector = self.make_api()
        logical_server = object()
        server_list = SimpleNamespace(
            logicals=[logical_server],
            user_tier=2,
            get_available_servers=Mock(return_value=iter([logical_server])),
            get_servers_with_features=Mock(return_value=iter([logical_server])),
            get_fastest_server=Mock(return_value=logical_server),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = self.make_adapter(api)
        adapter._connector = connector
        adapter._logged_in = True

        await adapter.connect_fastest_with_features(("p2p", "streaming"))

        server_list.get_available_servers.assert_called_once_with(
            server_list.logicals, server_list.user_tier
        )
        server_list.get_servers_with_features.assert_called_once()
        _, filter_kwargs = server_list.get_servers_with_features.call_args
        self.assertEqual(
            ServerFeatureEnum.P2P | ServerFeatureEnum.STREAMING,
            filter_kwargs["request_features"],
        )
        self.assertEqual(
            ServerFeatureEnum(0),
            filter_kwargs["exclude_features"],
        )
        server_list.get_fastest_server.assert_called_once()
        connector.get_vpn_server.assert_called_once_with(
            logical_server, "client-config"
        )
        connector.connect.assert_awaited_once_with("vpn-server", protocol="wireguard")

    async def test_capability_connect_rejects_unknown_or_unavailable_selection(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        adapter._connector = connector
        adapter._logged_in = True

        with self.assertRaisesRegex(ValueError, "supported Proton server capabilities"):
            await adapter.connect_fastest_with_features(("random",))

        server_list = SimpleNamespace(
            logicals=[],
            user_tier=2,
            get_available_servers=Mock(return_value=iter(())),
            get_servers_with_features=Mock(return_value=iter(())),
            get_fastest_server=Mock(return_value=None),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        with self.assertRaisesRegex(RuntimeError, "current tier"):
            await adapter.connect_fastest_with_features(("tor", "p2p"))

        connector.connect.assert_not_awaited()

    async def test_scoped_capability_connect_uses_only_the_selected_pool(self):
        api, connector = self.make_api()
        country_server = object()
        group_server = object()
        group = SimpleNamespace(name="Zurich", servers=[group_server])
        country = SimpleNamespace(
            code="CH",
            servers=[country_server, group_server],
            locations=[group],
            secure_core_group=None,
        )
        server_list = SimpleNamespace(
            logicals=[country_server, group_server],
            user_tier=2,
            group_by_country=Mock(return_value=[country]),
            get_available_servers=Mock(side_effect=lambda items, _: iter(items)),
            get_servers_with_features=Mock(side_effect=lambda items, **_: iter(items)),
            get_fastest_server=Mock(side_effect=[country_server, group_server]),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = self.make_adapter(api)
        adapter._connector = connector
        adapter._logged_in = True

        await adapter.connect_country_with_features("CH", ("p2p",))
        self.assertIs(
            server_list.get_available_servers.call_args_list[0].args[0],
            country.servers,
        )

        await adapter.connect_group_with_features(
            "CH", "location", "Zurich", ("streaming",)
        )
        self.assertIs(
            server_list.get_available_servers.call_args_list[1].args[0],
            group.servers,
        )
        self.assertEqual(2, connector.connect.await_count)

    async def test_settings_round_trip_uses_official_core_objects(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        current = await adapter.get_settings()
        self.assertEqual("wireguard", current.protocol)
        self.assertEqual("WireGuard", current.protocols[0].name)
        self.assertEqual(1, current.net_shield)
        self.assertTrue(current.protocol_editable)

        updated = await adapter.update_settings(
            {"netShield": 2, "vpnAccelerator": False, "ipv6": False}
        )

        api.save_settings.assert_awaited_once()
        saved = api.save_settings.await_args.args[0]
        self.assertEqual(2, saved.features.netshield)
        self.assertFalse(saved.features.vpn_accelerator)
        self.assertFalse(saved.ipv6)
        self.assertEqual(2, updated.net_shield)
        connector.connect.assert_not_awaited()

    async def test_settings_read_does_not_mutate_snapshot_kill_switch_state(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        adapter._kill_switch = 0
        api.load_settings.return_value.killswitch = 2

        current = await adapter.get_settings()

        self.assertEqual(2, current.kill_switch)
        self.assertEqual(0, adapter._kill_switch)
        api.save_settings.assert_not_awaited()

    async def test_delayed_settings_read_cannot_restore_state_after_logout(self):
        api, _ = self.make_api()
        current_settings = api.load_settings.return_value
        current_settings.killswitch = 2
        stale_settings = copy.deepcopy(current_settings)
        stale_read_started = asyncio.Event()
        release_stale_read = asyncio.Event()
        load_count = 0
        persisted_kill_switch = 2

        async def load_settings():
            nonlocal load_count
            load_count += 1
            if load_count == 1:
                stale_read_started.set()
                await release_stale_read.wait()
                return stale_settings
            return current_settings

        async def save_settings(settings):
            nonlocal persisted_kill_switch
            persisted_kill_switch = int(settings.killswitch)

        api.load_settings.side_effect = load_settings
        api.save_settings.side_effect = save_settings
        controller = BackendController(self.make_adapter(api))
        self.assertTrue(await controller.start())

        stale_read = asyncio.create_task(controller.get_settings_json())
        await asyncio.wait_for(stale_read_started.wait(), timeout=5)
        await controller.logout()
        self.assertEqual(0, persisted_kill_switch)

        release_stale_read.set()
        with self.assertRaisesRegex(RuntimeError, "session changed"):
            await stale_read

        self.assertEqual(0, persisted_kill_switch)
        self.assertEqual(1, api.save_settings.await_count)

    async def test_unofficial_build_reads_crash_reporting_without_writing(self):
        api, _ = self.make_api()
        persisted = api.load_settings.return_value
        persisted.anonymous_crash_reports = True
        api.usage_reporting.enabled = True
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        current = await adapter.get_settings()
        again = await adapter.get_settings()

        self.assertFalse(current.anonymous_crash_reports)
        self.assertFalse(again.anonymous_crash_reports)
        self.assertTrue(persisted.anonymous_crash_reports)
        self.assertFalse(api.usage_reporting.enabled)
        api.save_settings.assert_not_awaited()

    async def test_unofficial_build_rejects_crash_reporting_enable(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "unofficial community build"):
            await adapter.update_settings({"anonymousCrashReports": True})

        api.load_settings.assert_not_awaited()
        api.save_settings.assert_not_awaited()

    async def test_unofficial_build_persists_disabled_policy_on_explicit_write(self):
        api, _ = self.make_api()
        api.load_settings.return_value.anonymous_crash_reports = True
        api.usage_reporting.enabled = True
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        await adapter.update_settings({"ipv6": False})

        self.assertFalse(api.usage_reporting.enabled)
        self.assertFalse(api.save_settings.await_args.args[0].anonymous_crash_reports)

    async def test_approved_build_preserves_crash_reporting_preference(self):
        api, _ = self.make_api()
        api.load_settings.return_value.anonymous_crash_reports = True
        api.usage_reporting.enabled = True
        adapter = self.make_adapter(api, crash_report_submission_enabled=True)
        await adapter.initialize(Mock())

        current = await adapter.get_settings()

        self.assertTrue(current.anonymous_crash_reports)
        self.assertTrue(api.usage_reporting.enabled)
        api.save_settings.assert_not_awaited()

    async def test_connection_sensitive_settings_require_disconnect(self):
        api, connector = self.make_api()
        connector.current_state = state_named("Connected")
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "Disconnect"):
            await adapter.update_settings({"protocol": "wireguard"})
        with self.assertRaisesRegex(RuntimeError, "Disconnect"):
            await adapter.update_settings({"killSwitch": 1})

        api.save_settings.assert_not_awaited()

    async def test_packet_capture_uses_connected_protocol_and_selected_folder(self):
        api, connector = self.make_api()
        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )

        async def start_capture():
            # The durable handoff must exist before Core can accept the start.
            self.assertTrue(recovery_path.is_file())

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(side_effect=start_capture),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api)
        snapshots = []
        await adapter.initialize(snapshots.append)

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            self.assertEqual(
                capture_directory,
                connection.settings.packet_capture.directory_path,
            )
        connection.start_packet_capture.assert_awaited_once_with()
        self.assertTrue(snapshots[-1].packet_capture_active)

        await adapter.stop_packet_capture()
        connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(snapshots[-1].packet_capture_active)
        self.assertFalse(recovery_path.exists())

    async def test_controller_disconnect_expiry_preserves_core_save_without_late_down(self):
        api, connector = self.make_api()
        entered, release = asyncio.Event(), asyncio.Event()
        connector.current_state = state_named("Connected")

        async def save_settings(_settings):
            entered.set()
            await release.wait()

        api.save_settings.side_effect = save_settings
        adapter = self.make_adapter(api)
        controller = BackendController(adapter, cleanup_seconds=0.02)
        self.assertTrue(await controller.start())
        save = asyncio.create_task(controller.update_settings_json('{"ipv6":false}'))
        await asyncio.wait_for(entered.wait(), 1)
        try:
            with self.assertRaisesRegex(RuntimeError, "could not be dispatched"):
                await asyncio.wait_for(controller.disconnect(), 0.5)
            self.assertFalse(save.done())
            self.assertEqual(0, save.cancelling())
            self.assertTrue(controller.snapshot.busy)
            connector.disconnect.assert_not_awaited()
        finally:
            release.set()
            await save
        connector.disconnect.assert_not_awaited()
        self.assertEqual("connected", controller.snapshot.state)
        self.assertEqual(1, api.save_settings.await_count)
        await controller.disconnect()
        connector.disconnect.assert_awaited_once_with()
        await controller.close()

    async def test_controller_stop_bypasses_save_but_down_waits_for_protection_apply(self):
        api, connector = self.make_api()
        save_entered = asyncio.Event()
        release_save = asyncio.Event()
        order = []

        async def save_settings(_settings):
            save_entered.set()
            await release_save.wait()
            order.append("saved")

        async def stop_capture():
            order.append("capture-stopped")

        async def disconnect():
            order.append("down")
            connector.current_state = state_named("Disconnected")

        api.save_settings.side_effect = save_settings
        connector.disconnect.side_effect = disconnect
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(side_effect=stop_capture),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api)
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())
        with tempfile.TemporaryDirectory() as capture_directory:
            await controller.start_packet_capture(capture_directory)
            # Core save_settings reapplies protection even for a permitted
            # connected-state preference such as IPv6.
            save = asyncio.create_task(controller.update_settings_json('{"ipv6":false}'))
            await asyncio.wait_for(save_entered.wait(), 1)
            down = asyncio.create_task(controller.disconnect())
            stop = asyncio.create_task(controller.stop_packet_capture())
            try:
                done, _ = await asyncio.wait({stop}, timeout=1)
                self.assertIn(stop, done)
                stop.result()
                self.assertEqual(["capture-stopped"], order)
                self.assertFalse(save.done())
                self.assertTrue(controller.snapshot.busy)
                self.assertFalse(controller.snapshot.packet_capture_active)
                connector.disconnect.assert_not_awaited()
            finally:
                release_save.set()
                await asyncio.gather(save, down, stop)
                order_before_close = list(order)
                await controller.close()
        self.assertEqual(["capture-stopped", "saved", "down"], order_before_close)
        connection.stop_packet_capture.assert_awaited_once_with()

    async def test_session_expiry_cannot_overtake_capture_start(self):
        api, connector = self.make_api()
        start_entered = asyncio.Event()
        release_start = asyncio.Event()

        async def start_capture():
            start_entered.set()
            await release_start.wait()

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(side_effect=start_capture),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with tempfile.TemporaryDirectory() as capture_directory:
            capture_start = asyncio.create_task(
                adapter.start_packet_capture(capture_directory)
            )
            await asyncio.wait_for(start_entered.wait(), timeout=5)
            expired_error = type(
                "ProtonAPIAuthenticationNeeded", (Exception,), {}
            )
            api.load_settings.side_effect = expired_error()
            expiring_read = asyncio.create_task(adapter.get_settings())
            await asyncio.sleep(0)

            self.assertFalse(expiring_read.done())
            self.assertTrue(adapter._logged_in)
            release_start.set()
            await capture_start
            with self.assertRaisesRegex(RuntimeError, "session expired"):
                await expiring_read

        self.assertFalse(adapter._logged_in)
        self.assertEqual("expired", snapshots[-1].auth_state)
        await adapter.stop_packet_capture()

    async def test_rejected_capture_directory_remains_inactive_and_retryable(self):
        class RejectingCaptureSettings:
            max_bytes = 512 * 1024 * 1024

            @property
            def directory_path(self):
                return "/tmp"

            @directory_path.setter
            def directory_path(self, _value):
                raise RuntimeError("provider detail must remain private")

        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(packet_capture=RejectingCaptureSettings()),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            for _attempt in range(2):
                with self.assertRaisesRegex(
                    RuntimeError, "Proton could not configure packet capture"
                ) as failure:
                    await adapter.start_packet_capture(capture_directory)
                self.assertNotIn("provider detail", str(failure.exception))

        connection.start_packet_capture.assert_not_awaited()
        connection.stop_packet_capture.assert_not_awaited()
        self.assertFalse(adapter._packet_capture_active)
        self.assertIsNone(adapter._packet_capture_watchdog_task)

    async def test_cancelled_packet_capture_start_is_compensated(self):
        api, connector = self.make_api()
        start_entered = asyncio.Event()
        never_finishes = asyncio.Event()

        async def start_capture():
            start_entered.set()
            await never_finishes.wait()

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(side_effect=start_capture),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            start_task = asyncio.create_task(
                adapter.start_packet_capture(capture_directory)
            )
            await asyncio.wait_for(start_entered.wait(), timeout=1.0)
            start_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await start_task

        connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(adapter._packet_capture_active)
        self.assertIsNone(adapter._packet_capture_watchdog_task)

    async def test_late_packet_capture_start_failure_is_compensated(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(
                side_effect=RuntimeError("late start acknowledgement")
            ),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            with self.assertRaisesRegex(
                RuntimeError, "Proton could not start packet capture"
            ) as failure:
                await adapter.start_packet_capture(capture_directory)

        self.assertNotIn("acknowledgement", str(failure.exception))
        connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(adapter._packet_capture_active)
        self.assertIsNone(adapter._packet_capture_watchdog_task)

    async def test_hanging_capture_stop_cannot_stall_backend_shutdown(self):
        api, connector = self.make_api()
        start_entered = asyncio.Event()
        never_finishes = asyncio.Event()

        async def start_capture():
            start_entered.set()
            await never_finishes.wait()

        async def stop_capture():
            await never_finishes.wait()

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(side_effect=start_capture),
            stop_packet_capture=AsyncMock(side_effect=stop_capture),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = ProtonCoreAdapter(
            api, packet_capture_stop_attempt_seconds=0.01
        )
        controller = BackendController(adapter, shutdown_drain_seconds=0.04)
        self.assertTrue(await controller.start())

        with tempfile.TemporaryDirectory() as capture_directory:
            start_task = asyncio.create_task(
                controller.start_packet_capture(capture_directory)
            )
            await asyncio.wait_for(start_entered.wait(), timeout=1.0)
            await asyncio.wait_for(controller.close(), timeout=0.5)

        self.assertTrue(start_task.cancelled())
        self.assertGreaterEqual(connection.stop_packet_capture.await_count, 4)
        self.assertIsNone(adapter._packet_capture_watchdog_task)
        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )
        self.assertTrue(recovery_path.is_file())

    async def test_restarted_backend_stops_unconfirmed_packet_capture(self):
        api, connector = self.make_api()
        never_finishes = asyncio.Event()

        async def stop_capture():
            await never_finishes.wait()

        first_connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(side_effect=stop_capture),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = first_connection
        first = self.make_adapter(api, packet_capture_stop_attempt_seconds=0.01)
        await first.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            await first.start_packet_capture(capture_directory)
            await asyncio.wait_for(first.close(), timeout=0.5)

        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )
        self.assertTrue(recovery_path.is_file())
        self.assertTrue(first._packet_capture_active)
        self.assertIsNone(first._packet_capture_watchdog_task)

        replacement_connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=first_connection.settings,
            supports_packet_capture=Mock(return_value=True),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_connection = replacement_connection
        replacement = ProtonCoreAdapter(
            api, packet_capture_stop_attempt_seconds=0.01
        )

        snapshot = await replacement.initialize(Mock())

        replacement_connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(snapshot.packet_capture_active)
        self.assertFalse(recovery_path.exists())

    async def test_recovery_without_connection_fails_closed_and_keeps_marker(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(side_effect=RuntimeError("unavailable")),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        first = self.make_adapter(api, packet_capture_stop_attempt_seconds=0.01)
        await first.initialize(Mock())
        with tempfile.TemporaryDirectory() as capture_directory:
            await first.start_packet_capture(capture_directory)
            await first.close()

        recovery_path = Path(os.environ["XDG_RUNTIME_DIR"]) / (
            PACKET_CAPTURE_RECOVERY_FILENAME
        )
        connector.current_connection = None
        replacement = ProtonCoreAdapter(
            api, packet_capture_stop_attempt_seconds=0.01
        )

        with self.assertRaisesRegex(RuntimeError, "backend will retry"):
            await replacement.initialize(Mock())

        self.assertTrue(recovery_path.is_file())

    async def test_packet_capture_fails_closed_without_core_byte_limit(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(directory_path="/tmp")
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            with self.assertRaisesRegex(RuntimeError, "byte limit"):
                await adapter.start_packet_capture(capture_directory)

        connection.start_packet_capture.assert_not_awaited()

    async def test_packet_capture_cannot_replace_an_active_generation(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            with self.assertRaisesRegex(RuntimeError, "already active"):
                await adapter.start_packet_capture(capture_directory)

        connection.start_packet_capture.assert_awaited_once_with()
        await adapter.stop_packet_capture()

    async def test_packet_capture_watchdog_stops_once_and_clears_state(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        snapshots = []
        adapter = self.make_adapter(api, packet_capture_max_seconds=0.01)
        await adapter.initialize(snapshots.append)

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            await asyncio.sleep(0.05)

        connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(snapshots[-1].packet_capture_active)
        self.assertIn("safety limit", snapshots[-1].message)

    async def test_packet_capture_watchdog_retries_past_deadline_until_confirmed(self):
        api, connector = self.make_api()
        stop_attempts = 0

        async def stop_capture():
            nonlocal stop_attempts
            stop_attempts += 1
            if stop_attempts <= 3:
                raise RuntimeError("temporarily unavailable")

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(side_effect=stop_capture),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        snapshots = []
        adapter = ProtonCoreAdapter(
            api,
            packet_capture_max_seconds=0.01,
            packet_capture_stop_attempt_seconds=0.01,
        )
        await adapter.initialize(snapshots.append)

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            await asyncio.sleep(0.1)

        self.assertEqual(4, stop_attempts)
        self.assertFalse(adapter._packet_capture_active)
        self.assertIn("safety limit", snapshots[-1].message)

    async def test_manual_packet_capture_stop_cancels_watchdog(self):
        api, connector = self.make_api()
        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api, packet_capture_max_seconds=0.02)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            await adapter.stop_packet_capture()
            await asyncio.sleep(0.05)

        connection.stop_packet_capture.assert_awaited_once_with()

    async def test_manual_stop_racing_watchdog_calls_core_once(self):
        api, connector = self.make_api()
        stop_entered = asyncio.Event()
        release_stop = asyncio.Event()

        async def stop_capture():
            stop_entered.set()
            await release_stop.wait()

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(
                packet_capture=SimpleNamespace(
                    directory_path="/tmp", max_bytes=512 * 1024 * 1024
                )
            ),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(side_effect=stop_capture),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api, packet_capture_max_seconds=0.01)
        await adapter.initialize(Mock())

        with tempfile.TemporaryDirectory() as capture_directory:
            await adapter.start_packet_capture(capture_directory)
            await asyncio.wait_for(stop_entered.wait(), timeout=1.0)
            manual_stop = asyncio.create_task(adapter.stop_packet_capture())
            await asyncio.sleep(0)
            release_stop.set()
            await asyncio.wait_for(manual_stop, timeout=1.0)

        connection.stop_packet_capture.assert_awaited_once_with()
        self.assertFalse(adapter._packet_capture_active)

    async def test_settings_conflicts_are_rejected_without_side_effects(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.features.split_tunneling.enabled = True
        settings.custom_dns.enabled = True
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(ValueError, "split tunneling"):
            await adapter.update_settings({"killSwitch": 1})
        with self.assertRaisesRegex(ValueError, "custom DNS"):
            await adapter.update_settings({"netShield": 2})

        api.save_settings.assert_not_awaited()

    async def test_settings_core_failures_are_sanitized(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        api.load_settings.side_effect = RuntimeError("token=must-not-escape")
        with self.assertRaisesRegex(
            RuntimeError, "Proton could not load the VPN settings"
        ) as load_error:
            await adapter.get_settings()
        self.assertNotIn("must-not-escape", str(load_error.exception))

        api.load_settings.side_effect = None
        api.save_settings.side_effect = RuntimeError("secret=must-not-escape")
        with self.assertRaisesRegex(
            RuntimeError, "Proton could not .*VPN settings"
        ) as save_error:
            await adapter.update_settings({"ipv6": False})
        self.assertNotIn("must-not-escape", str(save_error.exception))

    async def test_failed_kill_switch_save_restores_persisted_and_live_state(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 0
        persisted_kill_switch = 0
        live_kill_switch = 0
        write_order = []

        async def commit_then_fail(saved_settings):
            nonlocal persisted_kill_switch, live_kill_switch
            value = int(saved_settings.killswitch)
            write_order.append(value)
            persisted_kill_switch = value
            if len(write_order) == 1:
                raise RuntimeError("connector application failed")
            live_kill_switch = value

        api.save_settings.side_effect = commit_then_fail
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "save the VPN settings"):
            await adapter.update_settings({"killSwitch": 2})

        self.assertEqual([2, 0], write_order)
        self.assertEqual(0, persisted_kill_switch)
        self.assertEqual(0, live_kill_switch)
        self.assertTrue(adapter._logged_in)

    async def test_failed_kill_switch_compensation_requires_recovery(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 0
        snapshots = []
        api.save_settings.side_effect = [
            RuntimeError("late acknowledgement failure"),
            RuntimeError("compensation failed"),
        ]
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "could not confirm"):
            await adapter.update_settings({"killSwitch": 2})

        self.assertFalse(adapter._logged_in)
        self.assertEqual("protection_unknown", snapshots[-1].auth_state)
        self.assertEqual(0, snapshots[-1].kill_switch)

    async def test_failed_generic_setting_compensation_blocks_operations(self):
        api, _ = self.make_api()
        snapshots = []
        api.save_settings.side_effect = [
            RuntimeError("late acknowledgement failure"),
            RuntimeError("compensation failed"),
        ]
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with self.assertRaisesRegex(RuntimeError, "could not confirm"):
            await adapter.update_settings({"netShield": 2})

        self.assertFalse(adapter._logged_in)
        self.assertEqual("settings_unavailable", snapshots[-1].auth_state)
        self.assertIn("restart", snapshots[-1].message)

    async def test_timed_out_settings_compensation_retains_executor_write(self):
        api, _ = self.make_api()
        compensation_started = asyncio.Event()
        release_write = threading.Event()
        write_finished = threading.Event()
        write_order = []
        save_calls = 0

        async def save_with_blocked_compensation(settings):
            nonlocal save_calls
            save_calls += 1
            value = int(settings.features.netshield)
            if save_calls == 1:
                write_order.append(value)
                raise RuntimeError("late acknowledgement failure")

            def complete_write():
                if not release_write.wait(timeout=2):
                    raise RuntimeError("test did not release compensation")
                write_order.append(value)
                write_finished.set()

            compensation_started.set()
            await asyncio.to_thread(complete_write)

        api.save_settings.side_effect = save_with_blocked_compensation
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with patch(
            "proton_vpn_kde_backend.adapters.LOGOUT_RECOVERY_TIMEOUT_SECONDS",
            0.01,
        ):
            update = asyncio.create_task(adapter.update_settings({"netShield": 2}))
            await asyncio.wait_for(compensation_started.wait(), timeout=5)
            try:
                await asyncio.sleep(0.03)
                update.cancel()
                await asyncio.sleep(0)
                update.cancel()
                await asyncio.sleep(0)
                self.assertFalse(update.done())
                self.assertFalse(write_finished.is_set())
                self.assertTrue(adapter._authentication_scope._lock.locked())
                self.assertEqual([2], write_order)
            finally:
                release_write.set()
                with self.assertRaises(asyncio.CancelledError):
                    await update

        self.assertTrue(write_finished.is_set())
        self.assertEqual([2, 1], write_order)
        self.assertEqual("settings_unavailable", snapshots[-1].auth_state)
        self.assertFalse(adapter._authentication_scope._lock.locked())

    async def test_expiry_after_compensation_stage_timeout_stays_authoritative(self):
        api, _ = self.make_api()
        expired_error = type("ProtonAPIAuthenticationNeeded", (Exception,), {})
        compensation_started = asyncio.Event()
        release_compensation = asyncio.Event()
        save_calls = 0

        async def expire_after_compensation(_settings):
            nonlocal save_calls
            save_calls += 1
            if save_calls == 1:
                raise RuntimeError("late acknowledgement failure")
            compensation_started.set()
            await release_compensation.wait()
            raise expired_error()

        api.save_settings.side_effect = expire_after_compensation
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        with patch(
            "proton_vpn_kde_backend.adapters.LOGOUT_RECOVERY_TIMEOUT_SECONDS",
            0.01,
        ):
            update = asyncio.create_task(adapter.update_settings({"netShield": 2}))
            await asyncio.wait_for(compensation_started.wait(), timeout=5)
            try:
                await asyncio.sleep(0.03)
                self.assertFalse(update.done())
            finally:
                release_compensation.set()
                with self.assertRaisesRegex(RuntimeError, "session expired"):
                    await update

        self.assertEqual("expired", snapshots[-1].auth_state)
        self.assertFalse(adapter._logged_in)

    async def test_cancelled_setting_save_finishes_before_compensation(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        first_save_started = asyncio.Event()
        release_first_save = asyncio.Event()
        write_order = []

        async def delayed_save(saved_settings):
            value = int(saved_settings.features.netshield)
            if not write_order:
                first_save_started.set()
                await release_first_save.wait()
            write_order.append(value)

        api.save_settings.side_effect = delayed_save
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        update_task = asyncio.create_task(
            adapter.update_settings({"netShield": 2})
        )
        await asyncio.wait_for(first_save_started.wait(), timeout=5)
        update_task.cancel()
        await asyncio.sleep(0)
        self.assertEqual([], write_order)
        release_first_save.set()
        with self.assertRaises(asyncio.CancelledError):
            await update_task

        self.assertEqual([2, 1], write_order)
        self.assertEqual(1, settings.features.netshield)
        self.assertTrue(adapter._logged_in)

    async def test_cancelled_unfinished_save_blocks_racing_compensation(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 0
        save_started = asyncio.Event()
        release_save = asyncio.Event()
        save_finished = asyncio.Event()
        persisted_kill_switch = 0

        async def blocked_save(saved_settings):
            nonlocal persisted_kill_switch
            value = int(saved_settings.killswitch)
            save_started.set()
            await release_save.wait()
            persisted_kill_switch = value
            save_finished.set()

        api.save_settings.side_effect = blocked_save
        snapshots = []
        adapter = self.make_adapter(api)
        await adapter.initialize(snapshots.append)

        update_task = asyncio.create_task(
            adapter.update_settings({"killSwitch": 2})
        )
        await asyncio.wait_for(save_started.wait(), timeout=5)
        update_task.cancel()
        with patch(
            "proton_vpn_kde_backend.adapters.LOGOUT_RECOVERY_TIMEOUT_SECONDS",
            0.01,
        ):
            try:
                await asyncio.sleep(0.03)
                self.assertFalse(update_task.done())
                self.assertFalse(save_finished.is_set())
                self.assertEqual(1, api.save_settings.await_count)
            finally:
                release_save.set()
                with self.assertRaises(asyncio.CancelledError):
                    await update_task

        self.assertTrue(save_started.is_set())
        self.assertEqual(1, api.save_settings.await_count)
        self.assertEqual("protection_unknown", snapshots[-1].auth_state)
        self.assertTrue(save_finished.is_set())
        self.assertEqual(2, persisted_kill_switch)
        self.assertEqual(1, api.save_settings.await_count)

    async def test_split_tunneling_round_trip_preserves_ip_ranges(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        current = await adapter.get_split_tunneling()
        self.assertTrue(current.available)
        self.assertEqual(("/usr/bin/firefox",), current.exclude_app_paths)
        self.assertEqual(("10.0.0.0/8",), current.exclude_ip_ranges)

        updated = await adapter.update_split_tunneling(
            {
                "excludeAppPaths": ["/usr/bin/firefox", "/usr/bin/thunderbird"],
                "excludeIpRanges": ["192.168.0.0/16", "2001:db8::/32"],
                "enabled": True,
            }
        )

        saved = api.save_settings.await_args.args[0]
        self.assertTrue(saved.features.split_tunneling.enabled)
        self.assertEqual(
            ["/usr/bin/firefox", "/usr/bin/thunderbird"],
            saved.features.split_tunneling.exclude.app_paths,
        )
        self.assertEqual(
            ["192.168.0.0/16", "2001:db8::/32"],
            saved.features.split_tunneling.exclude.ip_ranges,
        )
        self.assertEqual(
            ("192.168.0.0/16", "2001:db8::/32"),
            updated.exclude_ip_ranges,
        )
        self.assertTrue(updated.enabled)

    async def test_custom_dns_round_trip_uses_official_entries(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        settings.features.netshield = 0
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        current = await adapter.get_custom_dns()
        self.assertFalse(current.enabled)
        self.assertEqual("9.9.9.9", current.servers[0].address)
        self.assertFalse(current.servers[0].enabled)

        updated = await adapter.update_custom_dns(
            {
                "servers": [
                    {"address": "1.1.1.1", "enabled": True},
                    {"address": "2606:4700:4700::1111", "enabled": False},
                ],
                "enabled": True,
            }
        )

        saved = api.save_settings.await_args.args[0]
        self.assertTrue(saved.custom_dns.enabled)
        self.assertEqual("1.1.1.1", saved.custom_dns.ip_list[0].ip.compressed)
        self.assertTrue(saved.custom_dns.ip_list[0].enabled)
        self.assertFalse(saved.custom_dns.ip_list[1].enabled)
        self.assertTrue(updated.enabled)
        self.assertEqual(2, len(updated.servers))

    async def test_custom_dns_conflict_is_rejected_without_side_effects(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(ValueError, "Disable NetShield"):
            await adapter.update_custom_dns({"enabled": True})

        self.assertFalse(settings.custom_dns.enabled)
        self.assertEqual(1, settings.features.netshield)
        api.save_settings.assert_not_awaited()

    async def test_custom_dns_requires_paid_plan(self):
        api, _ = self.make_api()
        api.account_data.max_tier = 0
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(RuntimeError, "paid Proton VPN plan"):
            await adapter.update_custom_dns({"servers": []})

        api.save_settings.assert_not_awaited()

    async def test_split_tunneling_conflicts_do_not_mutate_other_settings(self):
        api, connector = self.make_api()
        settings = await api.load_settings()
        settings.killswitch = 1
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(ValueError, "kill switch"):
            await adapter.update_split_tunneling({"enabled": True})
        self.assertEqual(1, settings.killswitch)
        api.save_settings.assert_not_awaited()

        settings.killswitch = 0
        connector.is_split_tunneling_available = False
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            await adapter.update_split_tunneling({"enabled": True})
        api.save_settings.assert_not_awaited()

    async def test_include_mode_requires_a_target_before_enabling(self):
        api, _ = self.make_api()
        settings = await api.load_settings()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        with self.assertRaisesRegex(ValueError, "at least one included"):
            await adapter.update_split_tunneling({"mode": "include", "enabled": True})
        self.assertEqual("exclude", settings.features.split_tunneling.mode.value)
        self.assertFalse(settings.features.split_tunneling.enabled)
        api.save_settings.assert_not_awaited()

    async def test_location_queries_include_feature_aware_groups(self):
        from proton.vpn.session.servers import ServerFeatureEnum

        api, _ = self.make_api()

        def server(name, exit_country, location, load, features, entry_country=None):
            return SimpleNamespace(
                name=name,
                exit_country=exit_country,
                exit_country_name=exit_country,
                entry_country=entry_country or exit_country,
                location=location,
                load=load,
                features=features,
                enabled=True,
                under_maintenance=False,
                smart_routing=entry_country not in {None, exit_country},
            )

        normal = server("CH#10", "CH", "Zurich", 42, [ServerFeatureEnum.P2P])
        tor = server("CH-TOR#1", "CH", "Zurich", 27, [ServerFeatureEnum.TOR])
        secure_core = server(
            "CH-DE#1",
            "CH",
            "Zurich",
            35,
            [ServerFeatureEnum.SECURE_CORE],
            "DE",
        )
        us = server(
            "US-NY#5",
            "US",
            "New York, NY",
            18,
            [ServerFeatureEnum.STREAMING],
        )
        zurich_group = SimpleNamespace(
            name="Zurich",
            servers=[normal, tor],
            features={ServerFeatureEnum.P2P, ServerFeatureEnum.TOR},
            under_maintenance=False,
            smart_routing=False,
        )
        secure_core_group = SimpleNamespace(
            name="Via Secure Core",
            servers=[secure_core],
            features={ServerFeatureEnum.SECURE_CORE},
            under_maintenance=False,
            smart_routing=True,
        )
        countries = [
            SimpleNamespace(
                code="ch",
                servers=[normal, tor, secure_core],
                locations=[zurich_group],
                secure_core_group=secure_core_group,
            ),
            SimpleNamespace(
                code="us",
                servers=[us],
                locations=[],
                secure_core_group=None,
            ),
        ]
        servers = [normal, tor, secure_core, us]
        server_list = SimpleNamespace(
            logicals=servers,
            user_tier=2,
            group_by_country=Mock(return_value=countries),
            get_available_servers=Mock(side_effect=lambda items, *_: iter(items)),
            get_by_name=Mock(
                side_effect={server.name: server for server in servers}.__getitem__
            ),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = self.make_adapter(api)
        adapter._logged_in = True

        countries = await adapter.get_countries()
        groups = await adapter.get_server_groups("CH")
        secure_core_servers = await adapter.get_group_servers(
            "CH", "secure-core", "Via Secure Core"
        )
        location_servers = await adapter.get_group_servers("CH", "location", "Zurich")
        swiss_loads = await adapter.get_server_loads("CH")
        location_search = await adapter.search_locations("zur")
        server_search = await adapter.search_locations("ch#")

        self.assertEqual(["CH", "US"], [country.code for country in countries])
        self.assertEqual(["location", "secure-core"], [group.kind for group in groups])
        self.assertTrue(groups[0].tor)
        self.assertTrue(groups[1].secure_core)
        self.assertEqual("CH-DE#1", secure_core_servers[0].name)
        self.assertEqual("DE", secure_core_servers[0].entry_country)
        self.assertTrue(secure_core_servers[0].smart_routing)
        normal_info = next(item for item in location_servers if item.name == "CH#10")
        self.assertTrue(normal_info.p2p)
        self.assertFalse(normal_info.streaming)
        self.assertEqual(
            {"CH#10", "CH-TOR#1", "CH-DE#1"},
            {load.name for load in swiss_loads},
        )
        self.assertEqual(["Zurich"], [item.name for item in location_search])
        self.assertEqual(["CH#10"], [item.name for item in server_search])

    async def test_free_tier_location_queries_keep_paid_servers_visible(self):
        api, _ = self.make_api()
        api.account_data.max_tier = 0

        def server(name, country, load):
            return SimpleNamespace(
                name=name,
                exit_country=country,
                entry_country=country,
                location="",
                load=load,
                features=[],
                enabled=True,
                under_maintenance=False,
                smart_routing=False,
            )

        free_server = server("CH-FREE#1", "CH", 65)
        paid_server = server("US#1", "US", 5)
        paid_group = SimpleNamespace(name="New York", servers=[paid_server])
        countries = [
            SimpleNamespace(
                code="ch",
                servers=[free_server],
                locations=[],
                secure_core_group=None,
                free=True,
                under_maintenance=False,
            ),
            SimpleNamespace(
                code="us",
                servers=[paid_server],
                locations=[paid_group],
                secure_core_group=None,
                free=False,
                under_maintenance=False,
            ),
        ]
        server_list = SimpleNamespace(
            logicals=[paid_server, free_server],
            user_tier=0,
            group_by_country=Mock(return_value=countries),
            get_available_servers=Mock(
                side_effect=lambda items, *_: (
                    item for item in items if item is free_server
                )
            ),
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = self.make_adapter(api)
        adapter._logged_in = True

        country_info = await adapter.get_countries()
        server_info = await adapter.get_group_servers("US", "location", "New York")

        self.assertTrue(country_info[0].accessible)
        self.assertTrue(country_info[0].free)
        self.assertFalse(country_info[1].accessible)
        self.assertFalse(country_info[1].free)
        self.assertEqual(["US#1"], [item.name for item in server_info])
        self.assertFalse(server_info[0].accessible)

    async def test_targeted_connect_uses_official_server_lookup(self):
        api, connector = self.make_api()
        logical_server = object()
        group = SimpleNamespace(name="Zurich", servers=[logical_server])
        country = SimpleNamespace(code="ch", locations=[group], secure_core_group=None)
        server_list = SimpleNamespace(
            get_fastest_in_country=Mock(return_value=logical_server),
            get_by_name=Mock(return_value=logical_server),
            group_by_country=Mock(return_value=[country]),
            get_available_servers=Mock(return_value=[logical_server]),
            get_fastest_server=Mock(return_value=logical_server),
            user_tier=2,
        )
        api.refresher.get_up_to_date_server_list.return_value = server_list
        adapter = self.make_adapter(api)
        adapter._connector = connector
        adapter._logged_in = True

        await adapter.connect_country("CH")
        server_list.get_fastest_in_country.assert_called_once_with("CH")
        connector.connect.assert_awaited_once()

        connector.connect.reset_mock()
        await adapter.connect_server("CH#10")
        server_list.get_by_name.assert_called_once_with("CH#10")
        connector.connect.assert_awaited_once()

        connector.connect.reset_mock()
        await adapter.connect_group("CH", "location", "Zurich")
        server_list.get_fastest_server.assert_called_once()
        connector.connect.assert_awaited_once()

    async def test_cleanup_inherits_one_deadline_across_the_adapter(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        deadline = asyncio.get_running_loop().time() + 1
        with (
            patch.object(adapter, "_superseding_connection_targets", wraps=adapter._superseding_connection_targets) as supersede,
            patch.object(adapter, "_disconnect_until_stable", wraps=adapter._disconnect_until_stable) as down,
            patch.object(adapter._packet_capture, "stop", wraps=adapter._packet_capture.stop) as stop,
        ):
            await adapter.disconnect(deadline=deadline)
            await adapter.stop_packet_capture(deadline=deadline)
        supersede.assert_called_once_with(deadline=deadline)
        down.assert_awaited_once_with(deadline=deadline)
        stop.assert_awaited_once_with(deadline=deadline)
        self.assertFalse(adapter._capture_stop_tasks)

    async def test_expired_cleanup_cannot_begin_adapter_mutation(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        intent = adapter._connection_intent_generation
        with patch.object(adapter._packet_capture, "stop", wraps=adapter._packet_capture.stop) as stop:
            for call in (adapter.disconnect, adapter.stop_packet_capture):
                with self.assertRaisesRegex(RuntimeError, "could not be dispatched"):
                    await call(deadline=asyncio.get_running_loop().time() - 1)
        self.assertEqual(intent, adapter._connection_intent_generation)
        connector.disconnect.assert_not_awaited()
        stop.assert_not_awaited()

    async def test_disconnect_scope_wait_uses_failed_retirement_boundary_at_deadline(self):
        api, connector = self.make_api()
        terminal_exit = Mock(side_effect=RuntimeError("recorded terminal exit"))
        adapter = self.make_adapter(api, terminal_exit=terminal_exit)
        await adapter.initialize(Mock())
        async with adapter._connection_scope.enter():
            deadline = asyncio.get_running_loop().time() + 0.02
            with self.assertLogs("proton_vpn_kde_backend.adapters", level="CRITICAL"):
                operation = asyncio.create_task(adapter.disconnect(deadline=deadline))
                with self.assertRaisesRegex(RuntimeError, "recorded terminal exit"):
                    await asyncio.wait_for(operation, 0.5)
        terminal_exit.assert_called_once_with(1)
        connector.disconnect.assert_not_awaited()
        self.assertEqual(0, adapter._reconnector._suspend_count)

    async def test_disconnect_barrier_uses_remaining_not_fresh_retirement_budget(self):
        api, connector = self.make_api()
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        terminal_exit = Mock(side_effect=RuntimeError("recorded terminal exit"))
        adapter = self.make_adapter(api, terminal_exit=terminal_exit)
        await adapter.initialize(Mock())

        async def down():
            entered.set()
            await release.wait()
            connector.current_state = state_named("Disconnected")
            finished.set()

        connector.disconnect.side_effect = down
        try:
            with self.assertLogs("proton_vpn_kde_backend.adapters", level="CRITICAL"):
                with self.assertRaisesRegex(RuntimeError, "recorded terminal exit"):
                    await asyncio.wait_for(adapter.disconnect(deadline=asyncio.get_running_loop().time() + 0.02), 0.5)
            self.assertTrue(entered.is_set())
            self.assertFalse(finished.is_set())
            terminal_exit.assert_called_once_with(1)
        finally:
            release.set()
            await asyncio.wait_for(finished.wait(), 1)

    async def test_capture_stop_deadline_keeps_live_owner_and_durable_recovery(self):
        api, connector = self.make_api()
        entered, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        terminal_exit = Mock(side_effect=RuntimeError("recorded terminal exit"))

        async def stop():
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                await release.wait()

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(packet_capture=SimpleNamespace(
                directory_path="/tmp", max_bytes=512 * 1024 * 1024)),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(side_effect=stop),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api, terminal_exit=terminal_exit)
        await adapter.initialize(Mock())
        with tempfile.TemporaryDirectory() as directory:
            await adapter.start_packet_capture(directory)
            recorded_deadline = adapter._packet_capture._journal.load_deadline()
            try:
                with self.assertLogs("proton_vpn_kde_backend.adapters", level="CRITICAL"):
                    with self.assertRaisesRegex(RuntimeError, "recorded terminal exit"):
                        await asyncio.wait_for(adapter.stop_packet_capture(deadline=asyncio.get_running_loop().time() + 0.03), 0.5)
                await asyncio.wait_for(cancelled.wait(), 1)
                self.assertTrue(entered.is_set())
                self.assertTrue(adapter._packet_capture_active)
                self.assertEqual(recorded_deadline, adapter._packet_capture._journal.load_deadline())
                self.assertEqual(1, len(adapter._capture_stop_tasks))
                terminal_exit.assert_called_once_with(1)
            finally:
                release.set()
                await asyncio.gather(*adapter._capture_stop_tasks)
                adapter._cancel_packet_capture_watchdog()
        self.assertFalse(adapter._capture_stop_tasks)

    async def test_capture_stop_caller_cancellation_retains_provider_until_completion(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        entered, release = asyncio.Event(), asyncio.Event()

        async def stop(*, deadline):
            entered.set()
            await release.wait()

        adapter._packet_capture.stop = AsyncMock(side_effect=stop)
        operation = asyncio.create_task(adapter.stop_packet_capture())
        await asyncio.wait_for(entered.wait(), 1)
        operation.cancel()
        await asyncio.sleep(0)
        operation.cancel()
        try:
            self.assertFalse(operation.done())
            self.assertEqual(1, len(adapter._capture_stop_tasks))
            self.assertEqual(0, next(iter(adapter._capture_stop_tasks)).cancelling())
        finally:
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await operation
        self.assertFalse(adapter._capture_stop_tasks)

    async def test_close_unsubscribes_and_stops_refresher(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())

        await adapter.close()

        connector.unregister.assert_any_call(adapter)
        self.assertEqual(2, connector.unregister.call_count)
        api.refresher.disable.assert_awaited_once_with()
        api.refresher.set_server_list_updated_callback.assert_called_with(None)
        api.refresher.set_server_loads_updated_callback.assert_called_with(None)
        api.refresher.set_location_names_updated_callback.assert_called_with(None)

    async def test_close_result_is_singleflight_sticky_and_cancellation_safe(self):
        for terminal in ("success", "failure", "timeout"):
            with self.subTest(terminal=terminal):
                api, connector = self.make_api()
                adapter = self.make_adapter(api)
                await adapter.initialize(Mock())
                entered, release = asyncio.Event(), asyncio.Event()

                async def disable(entered=entered, release=release, terminal=terminal):
                    entered.set()
                    await release.wait()
                    if terminal == "failure":
                        raise RuntimeError("provider close failed")

                api.refresher.disable.side_effect = disable
                deadline = asyncio.get_running_loop().time() + (0.05 if terminal == "timeout" else 1)
                first = asyncio.create_task(adapter.close(deadline=deadline))
                await asyncio.wait_for(entered.wait(), 1)
                second = asyncio.create_task(adapter.close(deadline=deadline + 100))
                first.cancel()
                await asyncio.sleep(0)
                first.cancel()
                if terminal != "timeout":
                    release.set()
                try:
                    outcomes = await asyncio.gather(first, second, return_exceptions=True)
                    self.assertIsInstance(outcomes[0], asyncio.CancelledError)
                    if terminal == "success":
                        self.assertIsNone(outcomes[1])
                        await adapter.close()
                    else:
                        error_type = TimeoutError if terminal == "timeout" else RuntimeError
                        self.assertIsInstance(outcomes[1], error_type)
                        with self.assertRaises(error_type):
                            await adapter.close(deadline=deadline + 100)
                    if terminal == "timeout":
                        self.assertFalse(adapter._close_work_task.done())
                        self.assertEqual(0, adapter._close_work_task.cancelling())
                finally:
                    release.set()
                    await asyncio.gather(adapter._close_work_task, return_exceptions=True)
                api.refresher.disable.assert_awaited_once_with()
                connector.unregister.assert_any_call(adapter)

    async def test_close_inherits_deadline_at_each_teardown_boundary(self):
        api, _ = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        deadline = asyncio.get_running_loop().time() + 1
        with (
            patch.object(adapter, "_retire_refresher_error_handler", wraps=adapter._retire_refresher_error_handler) as handler,
            patch.object(adapter, "_superseding_connection_targets", wraps=adapter._superseding_connection_targets) as supersede,
            patch.object(adapter, "_disconnect_until_stable", wraps=adapter._disconnect_until_stable) as down,
            patch.object(adapter._reconnector, "disable", wraps=adapter._reconnector.disable) as disable,
        ):
            await adapter.close(deadline=deadline)
        handler.assert_awaited_once_with(deadline)
        supersede.assert_called_once_with(deadline=deadline)
        down.assert_awaited_once_with(deadline=deadline, transitional_only=True)
        disable.assert_awaited_once_with(deadline=deadline)

    async def test_expired_close_does_not_dispatch_core_teardown(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        now = asyncio.get_running_loop().time()
        for deadline in (now - 1, now + 100):
            with self.assertRaisesRegex(TimeoutError, "shutdown deadline"):
                await adapter.close(deadline=deadline)
        self.assertIsNone(adapter._close_work_task)
        connector.disconnect.assert_not_awaited()
        connector.unregister.assert_not_called()
        api.refresher.disable.assert_not_awaited()

    async def test_close_waiting_for_scope_cannot_dispatch_after_deadline(self):
        for scope_name in ("_authentication_scope", "_connection_scope"):
            with self.subTest(scope=scope_name):
                api, connector = self.make_api()
                adapter = self.make_adapter(api)
                await adapter.initialize(Mock())
                async with getattr(adapter, scope_name).enter():
                    with self.assertRaisesRegex(TimeoutError, "shutdown deadline"):
                        await adapter.close(deadline=asyncio.get_running_loop().time() + 0.03)
                    self.assertFalse(adapter._close_work_task.done())
                await asyncio.gather(adapter._close_work_task, return_exceptions=True)
                connector.disconnect.assert_not_awaited()
                connector.unregister.assert_not_called()
                api.refresher.disable.assert_not_awaited()
                # Late scope release and Error notifications cannot re-arm retry.
                connector.current_state = state_named("Error")
                adapter._reconnector.status_update(connector.current_state)
                adapter._reconnector.enable()
                self.assertIsNone(adapter._reconnector._retry_task)

    async def test_capture_stop_uses_remaining_shutdown_budget_and_keeps_recovery(self):
        api, connector = self.make_api()
        entered, release = asyncio.Event(), asyncio.Event()

        async def stop():
            entered.set()
            await release.wait()

        connection = SimpleNamespace(
            server_name="US-IL#42",
            settings=SimpleNamespace(packet_capture=SimpleNamespace(
                directory_path="/tmp", max_bytes=512 * 1024 * 1024)),
            supports_packet_capture=Mock(return_value=True),
            start_packet_capture=AsyncMock(),
            stop_packet_capture=AsyncMock(side_effect=stop),
        )
        connector.current_state = state_named("Connected")
        connector.current_connection = connection
        adapter = self.make_adapter(api, packet_capture_stop_attempt_seconds=5)
        await adapter.initialize(Mock())
        with tempfile.TemporaryDirectory() as directory:
            await adapter.start_packet_capture(directory)
            try:
                with self.assertRaisesRegex(TimeoutError, "shutdown deadline"):
                    await asyncio.wait_for(adapter.close(deadline=asyncio.get_running_loop().time() + 0.03), 0.5)
                self.assertTrue(entered.is_set())
                self.assertTrue(adapter._packet_capture_active)
                self.assertTrue(adapter._packet_capture.has_pending_recovery())
                api.refresher.disable.assert_not_awaited()
            finally:
                release.set()
                await asyncio.gather(adapter._close_work_task, return_exceptions=True)
                await adapter.stop_packet_capture()

    async def test_close_waits_for_reconnect_worker_before_core_teardown(self):
        api, connector = self.make_api()
        adapter = self.make_adapter(api)
        await adapter.initialize(Mock())
        release_connect = await self.start_cancellation_resistant_reconnect(
            adapter, connector
        )

        close_task = asyncio.create_task(adapter.close())
        try:
            for _ in range(20):
                if adapter._reconnector._retiring_retry_tasks:
                    break
                await asyncio.sleep(0)
            self.assertTrue(adapter._reconnector._retiring_retry_tasks)
            self.assertFalse(close_task.done())
            api.refresher.disable.assert_not_awaited()
            self.assertFalse(
                any(
                    call.args == (adapter,)
                    for call in connector.unregister.call_args_list
                )
            )

            release_connect.set()
            await asyncio.wait_for(close_task, timeout=1)
            api.refresher.disable.assert_awaited_once_with()
            connector.unregister.assert_any_call(adapter)
        finally:
            release_connect.set()
            if not close_task.done():
                await asyncio.wait_for(close_task, timeout=1)


if __name__ == "__main__":
    unittest.main()
