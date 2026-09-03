# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Desktop-neutral VPN state controller."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from dataclasses import replace
import json
import logging
from typing import Callable, Protocol

from .errors import (
    UserVisibleError,
    UserVisibleRuntimeError,
    UserVisibleValueError,
    bounded_user_message,
)
from .features import CRASH_REPORT_SUBMISSION_ENABLED
from .models import (
    SUPPORTED_SERVER_FEATURES,
    CountryInfo,
    CustomDnsCallback,
    CustomDnsServer,
    CustomDnsServerValue,
    CustomDnsSettings,
    CustomDnsValue,
    LocationInfo,
    LocationSearchInfo,
    NpsSurveyResponse,
    ProtocolInfo,
    ServerDataCallback,
    ServerGroupInfo,
    ServerInfo,
    ServerLoadInfo,
    SettingsCallback,
    SettingsValue,
    SnapshotCallback,
    SplitTunnelingCallback,
    SplitTunnelingSettings,
    SplitTunnelingValue,
    SupportReport,
    VpnSettings,
    VpnSnapshot,
    custom_dns_patch_from_json,
    location_list_to_json,
    normalize_server_features,
    settings_patch_from_json,
    split_tunneling_patch_from_json,
    validate_nps_survey_response,
    validate_support_report,
)


__all__ = [
    "SUPPORTED_SERVER_FEATURES",
    "BackendController",
    "CoreAdapter",
    "CountryInfo",
    "CustomDnsCallback",
    "CustomDnsServer",
    "CustomDnsServerValue",
    "CustomDnsSettings",
    "CustomDnsValue",
    "LocationInfo",
    "LocationSearchInfo",
    "NpsSurveyResponse",
    "ProtocolInfo",
    "ServerDataCallback",
    "ServerGroupInfo",
    "ServerInfo",
    "ServerLoadInfo",
    "SettingsCallback",
    "SettingsValue",
    "SnapshotCallback",
    "SplitTunnelingCallback",
    "SplitTunnelingSettings",
    "SplitTunnelingValue",
    "SupportReport",
    "VpnSettings",
    "VpnSnapshot",
    "custom_dns_patch_from_json",
    "location_list_to_json",
    "normalize_server_features",
    "settings_patch_from_json",
    "split_tunneling_patch_from_json",
    "validate_nps_survey_response",
    "validate_support_report",
]


logger = logging.getLogger(__name__)

RECOVERY_REQUIRED_AUTH_STATES = frozenset(
    {"authentication_unknown", "settings_unavailable", "protection_unknown"}
)
RECOVERY_REQUIRED_MESSAGE = (
    "Restart the Proton backend and review VPN settings before continuing"
)

class CoreAdapter(Protocol):
    """Minimal surface required from Proton's networking core."""

    async def initialize(
        self,
        callback: SnapshotCallback,
        server_data_callback: ServerDataCallback | None = None,
    ) -> VpnSnapshot: ...
    def has_pending_startup_recovery(self) -> bool: ...
    async def get_countries(self) -> list[CountryInfo]: ...
    async def get_server_groups(self, country_code: str) -> list[ServerGroupInfo]: ...
    async def get_group_servers(
        self, country_code: str, group_kind: str, group_name: str
    ) -> list[ServerInfo]: ...
    async def get_server_loads(self, country_code: str) -> list[ServerLoadInfo]: ...
    async def search_locations(self, query: str) -> list[LocationSearchInfo]: ...
    async def get_settings(self) -> VpnSettings: ...
    async def update_settings(self, patch: dict[str, SettingsValue]) -> VpnSettings: ...
    async def get_split_tunneling(self) -> SplitTunnelingSettings: ...
    async def update_split_tunneling(
        self, patch: dict[str, SplitTunnelingValue]
    ) -> SplitTunnelingSettings: ...
    async def get_custom_dns(self) -> CustomDnsSettings: ...
    async def update_custom_dns(
        self, patch: dict[str, CustomDnsValue]
    ) -> CustomDnsSettings: ...
    async def connect_fastest(self) -> None: ...
    async def connect_fastest_with_feature(self, feature: str) -> None: ...
    async def connect_fastest_with_features(
        self, features: tuple[str, ...]
    ) -> None: ...
    async def connect_country(self, country_code: str) -> None: ...
    async def connect_country_with_features(
        self, country_code: str, features: tuple[str, ...]
    ) -> None: ...
    async def connect_group(
        self, country_code: str, group_kind: str, group_name: str
    ) -> None: ...
    async def connect_group_with_features(
        self,
        country_code: str,
        group_kind: str,
        group_name: str,
        features: tuple[str, ...],
    ) -> None: ...
    async def connect_server(self, server_name: str) -> None: ...
    async def start_packet_capture(self, directory_path: str) -> None: ...
    async def stop_packet_capture(self) -> None: ...
    async def submit_support_report(self, report: SupportReport) -> None: ...
    async def take_pending_nps_survey(self) -> bool: ...
    async def submit_nps_survey(self, response: NpsSurveyResponse) -> None: ...
    async def login(self, username: str, password: str) -> None: ...
    async def submit_two_factor(self, code: str) -> None: ...
    async def cancel_login(self) -> None: ...
    async def begin_fido2(self) -> None: ...
    async def submit_fido2_pin(self, pin: str) -> None: ...
    async def cancel_fido2(self) -> None: ...
    async def logout(self) -> None: ...
    async def disable_kill_switch_for_login(self) -> None: ...
    async def set_reconnection_enabled(self, enabled: bool) -> None: ...
    async def disconnect(self) -> None: ...
    async def close(self) -> None: ...


class BackendController:
    """Serializes mutating operations and publishes immutable snapshots."""

    def __init__(
        self,
        adapter: CoreAdapter,
        *,
        crash_report_submission_enabled: bool = CRASH_REPORT_SUBMISSION_ENABLED,
        shutdown_drain_seconds: float = 5.0,
        packet_capture_shutdown_seconds: float = 20.0,
    ):
        self._adapter = adapter
        self._crash_report_submission_enabled = crash_report_submission_enabled
        self._snapshot = VpnSnapshot()
        self._listeners: list[SnapshotCallback] = []
        self._server_data_listeners: list[ServerDataCallback] = []
        self._settings_listeners: list[SettingsCallback] = []
        self._split_tunneling_listeners: list[SplitTunnelingCallback] = []
        self._custom_dns_listeners: list[CustomDnsCallback] = []
        self._operation_lock = asyncio.Lock()
        self._session_side_effect_lock = asyncio.Lock()
        # Core exposes settings, split tunneling, and custom DNS as projections
        # of one persisted settings object. Keep all six read/write entry points
        # in one completion order so an older read cannot arrive after a newer
        # successful mutation and repaint a client with stale state.
        self._settings_lock = asyncio.Lock()
        self._session_epoch = 0
        self._closing = False
        self._operation_busy = False
        self._active_operation_task: asyncio.Task[None] | None = None
        self._active_operation_kind: str | None = None
        self._preemptive_disconnect_tasks: set[asyncio.Task[None]] = set()
        self._active_session_side_effect_task: asyncio.Task[object] | None = None
        self._active_settings_task: asyncio.Task[object] | None = None
        self._active_account_read_tasks: set[asyncio.Task[object]] = set()
        self._abandoned_shutdown_tasks: set[asyncio.Task[object]] = set()
        self._close_task: asyncio.Task[None] | None = None
        self._adapter_close_task: asyncio.Task[None] | None = None
        self._packet_capture_start_task: asyncio.Task[None] | None = None
        self._shutdown_drain_seconds = max(0.0, shutdown_drain_seconds)
        self._packet_capture_shutdown_seconds = max(
            0.0, packet_capture_shutdown_seconds
        )

    @property
    def snapshot(self) -> VpnSnapshot:
        return self._snapshot

    def has_pending_startup_recovery(self) -> bool:
        return self._adapter.has_pending_startup_recovery()

    def subscribe(self, callback: SnapshotCallback) -> None:
        self._listeners.append(callback)

    def subscribe_server_data(self, callback: ServerDataCallback) -> None:
        self._server_data_listeners.append(callback)

    def subscribe_settings(self, callback: SettingsCallback) -> None:
        self._settings_listeners.append(callback)

    def subscribe_split_tunneling(self, callback: SplitTunnelingCallback) -> None:
        self._split_tunneling_listeners.append(callback)

    def subscribe_custom_dns(self, callback: CustomDnsCallback) -> None:
        self._custom_dns_listeners.append(callback)

    async def start(self) -> bool:
        try:
            snapshot = await self._adapter.initialize(
                self._on_adapter_snapshot,
                self._on_adapter_server_data,
            )
        except Exception as error:
            logger.error("Backend initialization failed (%s)", type(error).__name__)
            self._publish(
                replace(
                    self._snapshot,
                    ready=False,
                    state="error",
                    message="Backend initialization failed",
                )
            )
            return False
        self._publish(snapshot)
        return True

    async def connect_fastest(self) -> None:
        self._require_session()
        await self._run_operation(
            self._adapter.connect_fastest, operation_kind="connect"
        )

    async def connect_fastest_with_feature(self, feature: str) -> None:
        await self.connect_fastest_with_features([feature])

    async def connect_fastest_with_features(self, features: list[str]) -> None:
        self._require_session()
        normalized_features = normalize_server_features(features)
        if not normalized_features:
            await self._run_operation(
                self._adapter.connect_fastest, operation_kind="connect"
            )
            return
        await self._run_operation(
            lambda: self._adapter.connect_fastest_with_features(normalized_features),
            operation_kind="connect",
        )

    async def get_countries_json(self) -> str:
        async with self._accepted_account_read():
            session_epoch = self._current_session_epoch()
            countries = await self._adapter.get_countries()
            self._require_current_session(session_epoch)
        return location_list_to_json("countries", countries)

    async def get_server_groups_json(self, country_code: str) -> str:
        async with self._accepted_account_read():
            session_epoch = self._current_session_epoch()
            normalized_code = self._validate_country_code(country_code)
            groups = await self._adapter.get_server_groups(normalized_code)
            self._require_current_session(session_epoch)
        return location_list_to_json("groups", groups)

    async def get_group_servers_json(
        self, country_code: str, group_kind: str, group_name: str
    ) -> str:
        async with self._accepted_account_read():
            session_epoch = self._current_session_epoch()
            normalized_code = self._validate_country_code(country_code)
            normalized_kind, normalized_name = self._validate_server_group(
                group_kind, group_name
            )
            servers = await self._adapter.get_group_servers(
                normalized_code, normalized_kind, normalized_name
            )
            self._require_current_session(session_epoch)
        return location_list_to_json(
            "servers",
            servers,
        )

    async def get_server_loads_json(self, country_code: str) -> str:
        async with self._accepted_account_read():
            session_epoch = self._current_session_epoch()
            normalized_code = self._validate_country_code(country_code)
            loads = await self._adapter.get_server_loads(normalized_code)
            self._require_current_session(session_epoch)
        return location_list_to_json("loads", loads)

    async def search_locations_json(self, query: str) -> str:
        async with self._accepted_account_read():
            session_epoch = self._current_session_epoch()
            normalized_query = " ".join(query.split())
            if (
                not normalized_query
                or len(normalized_query) > 128
                or "\0" in normalized_query
            ):
                raise UserVisibleValueError("Enter a valid location search")
            results = await self._adapter.search_locations(normalized_query)
            self._require_current_session(session_epoch)
        return location_list_to_json("results", results)

    async def get_settings_json(self) -> str:
        session_epoch = self._current_session_epoch()
        async with self._serialized_settings_access():
            self._require_current_session(session_epoch)
            settings = await self._adapter.get_settings()
            self._require_current_session(session_epoch)
        return settings.to_json()

    async def get_pending_nps_survey_json(self) -> str:
        session_epoch = self._current_session_epoch()
        async with self._serialized_session_side_effect():
            self._require_current_session(session_epoch)
            available = await self._adapter.take_pending_nps_survey()
            self._require_current_session(session_epoch)
        return json.dumps(
            {"schemaVersion": 1, "available": available},
            separators=(",", ":"),
            sort_keys=True,
        )

    async def submit_nps_survey(
        self, score: str, comments: str, response_type: str
    ) -> None:
        session_epoch = self._current_session_epoch()
        response = validate_nps_survey_response(score, comments, response_type)
        async with self._serialized_session_side_effect():
            self._require_current_session(session_epoch)
            await self._adapter.submit_nps_survey(response)
            self._require_current_session(session_epoch)

    async def update_settings_json(self, patch_json: str) -> str:
        self._require_session()
        patch = settings_patch_from_json(patch_json)
        if (
            patch.get("anonymousCrashReports") is True
            and not self._crash_report_submission_enabled
        ):
            raise UserVisibleRuntimeError(
                "Anonymous crash reporting is disabled in this unofficial community build"
            )
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )
        async with self._serialized_operation():
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                async with self._serialized_settings_access():
                    settings = await self._adapter.update_settings(patch)
            except asyncio.CancelledError:
                self._publish(replace(self._snapshot, busy=False))
                raise
            except UserVisibleError as error:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message=bounded_user_message(
                            error, "The VPN settings could not be updated"
                        ),
                    )
                )
                raise
            except Exception:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message="The VPN settings could not be updated",
                    )
                )
                raise
            self._publish(replace(self._snapshot, busy=False))
        self._publish_settings(settings)
        return settings.to_json()

    async def get_split_tunneling_json(self) -> str:
        session_epoch = self._current_session_epoch()
        async with self._serialized_settings_access():
            self._require_current_session(session_epoch)
            settings = await self._adapter.get_split_tunneling()
            self._require_current_session(session_epoch)
        return settings.to_json()

    async def update_split_tunneling_json(self, patch_json: str) -> str:
        self._require_session()
        patch = split_tunneling_patch_from_json(patch_json)
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )
        async with self._serialized_operation():
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                async with self._serialized_settings_access():
                    split_tunneling = await self._adapter.update_split_tunneling(
                        patch
                    )
                    settings = await self._adapter.get_settings()
            except asyncio.CancelledError:
                self._publish(replace(self._snapshot, busy=False))
                raise
            except UserVisibleError as error:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message=bounded_user_message(
                            error,
                            "The split-tunneling settings could not be updated",
                        ),
                    )
                )
                raise
            except Exception:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message="The split-tunneling settings could not be updated",
                    )
                )
                raise
            self._publish(replace(self._snapshot, busy=False))
        self._publish_split_tunneling(split_tunneling)
        self._publish_settings(settings)
        return split_tunneling.to_json()

    async def get_custom_dns_json(self) -> str:
        session_epoch = self._current_session_epoch()
        async with self._serialized_settings_access():
            self._require_current_session(session_epoch)
            settings = await self._adapter.get_custom_dns()
            self._require_current_session(session_epoch)
        return settings.to_json()

    async def update_custom_dns_json(self, patch_json: str) -> str:
        self._require_session()
        patch = custom_dns_patch_from_json(patch_json)
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )
        async with self._serialized_operation():
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                async with self._serialized_settings_access():
                    custom_dns = await self._adapter.update_custom_dns(patch)
                    settings = await self._adapter.get_settings()
            except asyncio.CancelledError:
                self._publish(replace(self._snapshot, busy=False))
                raise
            except UserVisibleError as error:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message=bounded_user_message(
                            error, "The custom-DNS settings could not be updated"
                        ),
                    )
                )
                raise
            except Exception:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message="The custom-DNS settings could not be updated",
                    )
                )
                raise
            self._publish(replace(self._snapshot, busy=False))
        self._publish_custom_dns(custom_dns)
        self._publish_settings(settings)
        return custom_dns.to_json()

    async def connect_country(self, country_code: str) -> None:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        await self._run_operation(
            lambda: self._adapter.connect_country(normalized_code),
            operation_kind="connect",
        )

    async def connect_country_with_features(
        self, country_code: str, features: list[str]
    ) -> None:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        normalized_features = normalize_server_features(features)
        if not normalized_features:
            await self._run_operation(
                lambda: self._adapter.connect_country(normalized_code),
                operation_kind="connect",
            )
            return
        await self._run_operation(
            lambda: self._adapter.connect_country_with_features(
                normalized_code, normalized_features
            ),
            operation_kind="connect",
        )

    async def connect_group(
        self, country_code: str, group_kind: str, group_name: str
    ) -> None:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        normalized_kind, normalized_name = self._validate_server_group(
            group_kind, group_name
        )
        await self._run_operation(
            lambda: self._adapter.connect_group(
                normalized_code, normalized_kind, normalized_name
            ),
            operation_kind="connect",
        )

    async def connect_group_with_features(
        self,
        country_code: str,
        group_kind: str,
        group_name: str,
        features: list[str],
    ) -> None:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        normalized_kind, normalized_name = self._validate_server_group(
            group_kind, group_name
        )
        normalized_features = normalize_server_features(features)
        if not normalized_features:
            await self._run_operation(
                lambda: self._adapter.connect_group(
                    normalized_code, normalized_kind, normalized_name
                ),
                operation_kind="connect",
            )
            return
        await self._run_operation(
            lambda: self._adapter.connect_group_with_features(
                normalized_code,
                normalized_kind,
                normalized_name,
                normalized_features,
            ),
            operation_kind="connect",
        )

    async def connect_server(self, server_name: str) -> None:
        self._require_session()
        normalized_name = server_name.strip()
        if not normalized_name or len(normalized_name) > 128:
            raise UserVisibleValueError("Invalid Proton server name")
        await self._run_operation(
            lambda: self._adapter.connect_server(normalized_name),
            operation_kind="connect",
        )

    async def start_packet_capture(self, directory_path: str) -> None:
        self._require_session()
        if (
            not directory_path
            or len(directory_path) > 4096
            or "\0" in directory_path
            or "\n" in directory_path
            or "\r" in directory_path
        ):
            raise UserVisibleValueError("Select a valid packet-capture folder")
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("Packet capture requires an asyncio task")
        self._packet_capture_start_task = task
        try:
            await self._run_operation(
                lambda: self._adapter.start_packet_capture(directory_path)
            )
        finally:
            if self._packet_capture_start_task is task:
                self._packet_capture_start_task = None

    async def stop_packet_capture(self) -> None:
        self._require_cleanup_ready()
        session_epoch = self._session_epoch
        start_task = self._packet_capture_start_task
        if start_task is not None and start_task is not asyncio.current_task():
            # Stopping capture is risk-reducing. Cancel an accepted Start first
            # and wait for the adapter's cancellation compensation before the
            # idempotent Stop obtains the normal mutation lock.
            start_task.cancel()
            await asyncio.gather(start_task, return_exceptions=True)
        # Stop is risk-reducing cleanup. Queue it behind an unrelated mutation
        # instead of rejecting it, but never apply it after account replacement.
        async with self._serialized_operation():
            self._require_unchanged_session(session_epoch)
            await self._execute_operation(self._adapter.stop_packet_capture)

    async def submit_support_report(
        self,
        username: str,
        email: str,
        description: str,
        include_logs: str,
    ) -> None:
        self._require_session()
        report = validate_support_report(username, email, description, include_logs)
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )
        async with self._serialized_operation():
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                await self._adapter.submit_support_report(report)
            except asyncio.CancelledError:
                self._publish(replace(self._snapshot, busy=False))
                raise
            except UserVisibleError as error:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message=bounded_user_message(
                            error, "The issue report could not be submitted"
                        ),
                    )
                )
                raise
            except Exception:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message="The issue report could not be submitted",
                    )
                )
                raise
            self._publish(
                replace(
                    self._snapshot,
                    busy=False,
                    message="Your issue has been reported",
                )
            )

    async def login(self, username: str, password: str) -> None:
        self._require_ready()
        normalized_username = username.strip()
        if not normalized_username or len(normalized_username) > 320:
            raise UserVisibleValueError("Enter a valid Proton username")
        if not password or len(password) > 4096:
            raise UserVisibleValueError("Enter a valid Proton password")
        if self._snapshot.kill_switch == 2:
            raise UserVisibleRuntimeError(
                "Disable the permanent kill switch before signing in"
            )
        async def serialized_login() -> None:
            async with self._serialized_session_side_effect():
                await self._adapter.login(normalized_username, password)

        await self._run_operation(serialized_login)

    async def submit_two_factor(self, code: str) -> None:
        self._require_ready()
        normalized_code = code.strip()
        if len(normalized_code) not in {6, 8} or not normalized_code.isascii():
            raise UserVisibleValueError(
                "Enter a 6-digit code or an 8-character recovery code"
            )
        async def serialized_two_factor() -> None:
            async with self._serialized_session_side_effect():
                await self._adapter.submit_two_factor(normalized_code)

        await self._run_operation(serialized_two_factor)

    async def cancel_login(self) -> None:
        self._require_ready()

        async def serialized_cancel() -> None:
            async with self._serialized_session_side_effect():
                await self._adapter.cancel_login()

        await self._run_operation(serialized_cancel)

    async def begin_fido2(self) -> None:
        self._require_ready()

        async def serialized_fido2() -> None:
            async with self._serialized_session_side_effect():
                await self._adapter.begin_fido2()

        await self._run_operation(serialized_fido2)

    async def submit_fido2_pin(self, pin: str) -> None:
        self._require_ready()
        if not pin or len(pin) > 256:
            raise UserVisibleValueError("Enter the security-key PIN")
        await self._adapter.submit_fido2_pin(pin)

    async def cancel_fido2(self) -> None:
        self._require_ready()
        await self._adapter.cancel_fido2()

    async def logout(self) -> None:
        self._require_ready()

        async def serialized_logout() -> None:
            async with self._serialized_session_side_effect():
                await self._adapter.logout()

        await self._run_operation(serialized_logout)

    async def disable_kill_switch_for_login(self) -> None:
        self._require_ready()
        if self._snapshot.logged_in:
            raise UserVisibleRuntimeError("The Proton account is already signed in")
        await self._run_operation(self._adapter.disable_kill_switch_for_login)

    async def disconnect(self) -> None:
        # Disconnect is risk-reducing cleanup and remains available after an
        # account expiry strands an otherwise-live tunnel.
        self._require_cleanup_ready()
        if self._operation_lock.locked():
            if self._active_operation_kind != "connect":
                raise UserVisibleRuntimeError(
                    "Another VPN operation is already in progress"
                )
            # Admission follows semantic operation ownership, not a snapshot
            # that may lag before Connect publishes its first state.
            task = asyncio.current_task()
            if task is None:
                raise RuntimeError("Disconnect requires an asyncio task")
            self._preemptive_disconnect_tasks.add(task)
            self._publish(replace(self._snapshot, busy=True))
            try:
                await self._adapter.disconnect()
            finally:
                self._preemptive_disconnect_tasks.discard(task)
                self._publish(
                    replace(
                        self._snapshot,
                        busy=(
                            self._operation_busy
                            or bool(self._preemptive_disconnect_tasks)
                        ),
                    )
                )
            return
        await self._run_operation(self._adapter.disconnect)

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        # Preference updates arrive from both desktop processes. Serialize them
        # with logout/session expiry so a late update cannot re-enable the live
        # reconnector after the account has been signed out.
        async with self._serialized_operation():
            if self._closing:
                return
            await self._adapter.set_reconnection_enabled(enabled)

    async def close(self) -> None:
        """Join one authoritative shutdown, preserving its terminal outcome."""
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close_once())
        await asyncio.shield(self._close_task)

    async def _close_once(self) -> None:
        # The D-Bus object is unexported before this runs, so acquiring the
        # mutation lock first drains the accepted VPN operation, then settings
        # and session-side-effect locks drain independent accepted reads/survey
        # work. A stuck task is cancelled only after a bounded grace period;
        # adapter transactions perform their own cancellation-safe state repair
        # before unwinding.
        current_task = asyncio.current_task()
        capture_task = self._packet_capture_start_task
        if (
            capture_task is not None
            and capture_task is not current_task
            and not capture_task.done()
        ):
            # Capture Start owns mandatory, durable compensation that can take
            # three bounded Core stop attempts. Cancel it immediately and give
            # that safety protocol its explicit worst-case budget before the
            # ordinary mutation drain begins.
            capture_deadline = (
                asyncio.get_running_loop().time()
                + self._packet_capture_shutdown_seconds
            )
            await self._cancel_and_join_tasks(
                {capture_task}, capture_deadline
            )

        accepted_tasks = {
            task
            for task in (
                *self._preemptive_disconnect_tasks,
                self._active_operation_task,
                self._active_settings_task,
                self._active_session_side_effect_task,
                *self._active_account_read_tasks,
            )
            if task is not None and task is not current_task and not task.done()
        }
        deadline = (
            asyncio.get_running_loop().time() + self._shutdown_drain_seconds
        )
        await self._drain_accepted_tasks(accepted_tasks, deadline)

        acquired_locks: list[asyncio.Lock] = []
        try:
            for lock in (
                self._operation_lock,
                self._settings_lock,
                self._session_side_effect_lock,
            ):
                await self._acquire_before_deadline(lock, deadline)
                acquired_locks.append(lock)
            await self._close_adapter_before_deadline(deadline)
        finally:
            for lock in reversed(acquired_locks):
                lock.release()

    @staticmethod
    async def _cancel_and_join_tasks(
        tasks: set[asyncio.Task],
        deadline: float,
    ) -> None:
        for task in tasks:
            task.cancel()
        remaining = max(
            0.0, deadline - asyncio.get_running_loop().time()
        )
        pending = tasks
        if remaining:
            _, pending = await asyncio.wait(tasks, timeout=remaining)
        if pending:
            raise TimeoutError(
                "VPN safety cleanup did not stop before its shutdown deadline"
            )

    async def _drain_accepted_tasks(
        self,
        tasks: set[asyncio.Task],
        deadline: float,
    ) -> None:
        """Drain accepted work under one grace/cancellation deadline."""
        if not tasks:
            return
        loop = asyncio.get_running_loop()
        remaining = max(0.0, deadline - loop.time())
        _, pending = await asyncio.wait(tasks, timeout=remaining / 2)
        for task in pending:
            task.cancel()
        if pending:
            remaining = max(0.0, deadline - loop.time())
            if remaining:
                _, pending = await asyncio.wait(pending, timeout=remaining)
        if pending:
            raise TimeoutError(
                "Accepted VPN work did not stop before the shutdown deadline"
            )

    async def _close_adapter_before_deadline(self, deadline: float) -> None:
        """Bound final provider teardown without detaching it silently."""
        if self._adapter_close_task is None:
            self._adapter_close_task = asyncio.create_task(self._adapter.close())
        close_task = self._adapter_close_task
        remaining = max(
            0.0, deadline - asyncio.get_running_loop().time()
        )
        if remaining:
            done, _ = await asyncio.wait({close_task}, timeout=remaining)
            if close_task in done:
                close_task.result()
                return

        close_task.cancel()
        self._abandoned_shutdown_tasks.add(close_task)
        close_task.add_done_callback(self._finish_abandoned_shutdown_task)
        raise TimeoutError(
            "Proton Core teardown outlived the shutdown deadline"
        )

    def _finish_abandoned_shutdown_task(self, task: asyncio.Task[object]) -> None:
        self._abandoned_shutdown_tasks.discard(task)
        try:
            task.result()
        except (Exception, asyncio.CancelledError):
            pass

    @staticmethod
    async def _acquire_before_deadline(
        lock: asyncio.Lock,
        deadline: float,
    ) -> None:
        if not lock.locked():
            await lock.acquire()
            return
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(
                "VPN lifecycle ownership outlived the shutdown deadline"
            )
        try:
            await asyncio.wait_for(lock.acquire(), timeout=remaining)
        except TimeoutError:
            raise TimeoutError(
                "VPN lifecycle ownership outlived the shutdown deadline"
            ) from None

    def _require_session(self) -> None:
        self._require_ready()
        if not self._snapshot.logged_in:
            raise UserVisibleRuntimeError("A Proton account session is required")

    def _current_session_epoch(self) -> int:
        self._require_session()
        return self._session_epoch

    def _require_current_session(self, session_epoch: int) -> None:
        self._require_unchanged_session(session_epoch)
        if not self._snapshot.logged_in:
            raise UserVisibleRuntimeError("The Proton account session changed")

    def _require_unchanged_session(self, session_epoch: int) -> None:
        if session_epoch != self._session_epoch:
            raise UserVisibleRuntimeError("The Proton account session changed")

    def _require_ready(self) -> None:
        self._require_cleanup_ready()
        if self._snapshot.auth_state in RECOVERY_REQUIRED_AUTH_STATES:
            raise UserVisibleRuntimeError(RECOVERY_REQUIRED_MESSAGE)

    def _require_cleanup_ready(self) -> None:
        if self._closing:
            raise UserVisibleRuntimeError("The Proton backend is shutting down")
        if not self._snapshot.ready:
            raise UserVisibleRuntimeError("The Proton backend is not ready")

    @staticmethod
    def _validate_country_code(country_code: str) -> str:
        normalized_code = country_code.strip().upper()
        if (
            len(normalized_code) != 2
            or not normalized_code.isascii()
            or not normalized_code.isalpha()
        ):
            raise UserVisibleValueError("Invalid country code")
        return normalized_code

    @staticmethod
    def _validate_server_group(group_kind: str, group_name: str) -> tuple[str, str]:
        normalized_kind = group_kind.strip()
        normalized_name = group_name.strip()
        if normalized_kind not in {"location", "secure-core"}:
            raise UserVisibleValueError("Invalid Proton server group")
        if (
            not normalized_name
            or len(normalized_name) > 256
            or "\0" in normalized_name
            or "\n" in normalized_name
            or "\r" in normalized_name
        ):
            raise UserVisibleValueError("Invalid Proton server group name")
        return normalized_kind, normalized_name

    async def _run_operation(
        self,
        operation: Callable[[], Awaitable[None]],
        *,
        operation_kind: str = "mutation",
    ) -> None:
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )

        async with self._serialized_operation(operation_kind):
            await self._execute_operation(operation)

    async def _execute_operation(
        self, operation: Callable[[], Awaitable[None]]
    ) -> None:
        """Run one operation while the caller owns the serialization lock."""
        self._operation_busy = True
        self._publish(replace(self._snapshot, busy=True, message=""))
        try:
            await operation()
        except asyncio.CancelledError:
            self._operation_busy = False
            self._publish(
                replace(
                    self._snapshot,
                    busy=bool(self._preemptive_disconnect_tasks),
                )
            )
            raise
        except UserVisibleError as error:
            self._operation_busy = False
            self._publish(
                replace(
                    self._snapshot,
                    busy=bool(self._preemptive_disconnect_tasks),
                    message=bounded_user_message(
                        error, "The VPN operation could not be completed"
                    ),
                )
            )
            raise
        except Exception:
            self._operation_busy = False
            self._publish(
                replace(
                    self._snapshot,
                    busy=bool(self._preemptive_disconnect_tasks),
                    message="The VPN operation could not be completed",
                )
            )
            raise
        else:
            self._operation_busy = False
            self._publish(
                replace(
                    self._snapshot,
                    busy=bool(self._preemptive_disconnect_tasks),
                )
            )

    @asynccontextmanager
    async def _serialized_operation(
        self, operation_kind: str = "mutation"
    ) -> AsyncIterator[None]:
        await self._wait_for_preemptive_disconnects()
        async with self._operation_lock:
            if self._closing:
                raise UserVisibleRuntimeError(
                    "The Proton backend is shutting down"
                )
            task = asyncio.current_task()
            self._active_operation_task = task
            self._active_operation_kind = operation_kind
            try:
                yield
            finally:
                if self._active_operation_task is task:
                    self._active_operation_task = None
                    self._active_operation_kind = None

    async def _wait_for_preemptive_disconnects(self) -> None:
        current_task = asyncio.current_task()
        while True:
            active = tuple(
                task
                for task in self._preemptive_disconnect_tasks
                if task is not current_task and not task.done()
            )
            if not active:
                return
            await asyncio.shield(
                asyncio.gather(*active, return_exceptions=True)
            )

    @asynccontextmanager
    async def _accepted_account_read(self) -> AsyncIterator[None]:
        """Own a concurrent account read until completion or shutdown drain."""
        if self._closing:
            raise UserVisibleRuntimeError("The Proton backend is shutting down")
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("An account read requires an asyncio task")
        self._active_account_read_tasks.add(task)
        try:
            yield
        finally:
            self._active_account_read_tasks.discard(task)

    @asynccontextmanager
    async def _serialized_session_side_effect(self) -> AsyncIterator[None]:
        async with self._session_side_effect_lock:
            if self._closing:
                raise UserVisibleRuntimeError(
                    "The Proton backend is shutting down"
                )
            task = asyncio.current_task()
            self._active_session_side_effect_task = task
            try:
                yield
            finally:
                if self._active_session_side_effect_task is task:
                    self._active_session_side_effect_task = None

    @asynccontextmanager
    async def _serialized_settings_access(self) -> AsyncIterator[None]:
        async with self._settings_lock:
            if self._closing:
                raise UserVisibleRuntimeError(
                    "The Proton backend is shutting down"
                )
            task = asyncio.current_task()
            self._active_settings_task = task
            try:
                yield
            finally:
                if self._active_settings_task is task:
                    self._active_settings_task = None

    def _on_adapter_snapshot(self, snapshot: VpnSnapshot) -> None:
        if snapshot.logged_in != self._snapshot.logged_in:
            self._session_epoch += 1
        self._publish(replace(snapshot, busy=self._snapshot.busy))

    def _on_adapter_server_data(self, topology_changed: bool) -> None:
        for listener in tuple(self._server_data_listeners):
            listener(topology_changed)

    def _publish_settings(self, settings: VpnSettings) -> None:
        for listener in tuple(self._settings_listeners):
            listener(settings)

    def _publish_split_tunneling(self, settings: SplitTunnelingSettings) -> None:
        for listener in tuple(self._split_tunneling_listeners):
            listener(settings)

    def _publish_custom_dns(self, settings: CustomDnsSettings) -> None:
        for listener in tuple(self._custom_dns_listeners):
            listener(settings)

    def _publish(self, snapshot: VpnSnapshot) -> None:
        if snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        for listener in tuple(self._listeners):
            listener(snapshot)
