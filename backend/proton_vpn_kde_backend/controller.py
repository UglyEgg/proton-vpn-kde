# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Desktop-neutral VPN state controller."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import replace
import json
import logging
from typing import Callable, Protocol

from .errors import UserVisibleRuntimeError, UserVisibleValueError
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

class CoreAdapter(Protocol):
    """Minimal surface required from Proton's networking core."""

    async def initialize(
        self,
        callback: SnapshotCallback,
        server_data_callback: ServerDataCallback | None = None,
    ) -> VpnSnapshot: ...
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

    @property
    def snapshot(self) -> VpnSnapshot:
        return self._snapshot

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
        if not self._snapshot.logged_in:
            raise UserVisibleRuntimeError("A Proton account session is required")
        await self._run_operation(self._adapter.connect_fastest)

    async def connect_fastest_with_feature(self, feature: str) -> None:
        await self.connect_fastest_with_features([feature])

    async def connect_fastest_with_features(self, features: list[str]) -> None:
        self._require_session()
        normalized_features = normalize_server_features(features)
        if not normalized_features:
            await self._run_operation(self._adapter.connect_fastest)
            return
        await self._run_operation(
            lambda: self._adapter.connect_fastest_with_features(normalized_features)
        )

    async def get_countries_json(self) -> str:
        self._require_session()
        return location_list_to_json("countries", await self._adapter.get_countries())

    async def get_server_groups_json(self, country_code: str) -> str:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        return location_list_to_json(
            "groups", await self._adapter.get_server_groups(normalized_code)
        )

    async def get_group_servers_json(
        self, country_code: str, group_kind: str, group_name: str
    ) -> str:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        normalized_kind, normalized_name = self._validate_server_group(
            group_kind, group_name
        )
        return location_list_to_json(
            "servers",
            await self._adapter.get_group_servers(
                normalized_code, normalized_kind, normalized_name
            ),
        )

    async def get_server_loads_json(self, country_code: str) -> str:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        return location_list_to_json(
            "loads", await self._adapter.get_server_loads(normalized_code)
        )

    async def search_locations_json(self, query: str) -> str:
        self._require_session()
        normalized_query = " ".join(query.split())
        if (
            not normalized_query
            or len(normalized_query) > 128
            or "\0" in normalized_query
        ):
            raise UserVisibleValueError("Enter a valid location search")
        return location_list_to_json(
            "results", await self._adapter.search_locations(normalized_query)
        )

    async def get_settings_json(self) -> str:
        self._require_session()
        settings = await self._adapter.get_settings()
        self._publish_settings(settings)
        return settings.to_json()

    async def get_pending_nps_survey_json(self) -> str:
        self._require_session()
        available = await self._adapter.take_pending_nps_survey()
        return json.dumps(
            {"schemaVersion": 1, "available": available},
            separators=(",", ":"),
            sort_keys=True,
        )

    async def submit_nps_survey(
        self, score: str, comments: str, response_type: str
    ) -> None:
        self._require_session()
        response = validate_nps_survey_response(score, comments, response_type)
        await self._adapter.submit_nps_survey(response)

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
        async with self._operation_lock:
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                settings = await self._adapter.update_settings(patch)
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
        self._require_session()
        settings = await self._adapter.get_split_tunneling()
        self._publish_split_tunneling(settings)
        return settings.to_json()

    async def update_split_tunneling_json(self, patch_json: str) -> str:
        self._require_session()
        patch = split_tunneling_patch_from_json(patch_json)
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )
        async with self._operation_lock:
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                split_tunneling = await self._adapter.update_split_tunneling(patch)
                settings = await self._adapter.get_settings()
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
        self._require_session()
        settings = await self._adapter.get_custom_dns()
        self._publish_custom_dns(settings)
        return settings.to_json()

    async def update_custom_dns_json(self, patch_json: str) -> str:
        self._require_session()
        patch = custom_dns_patch_from_json(patch_json)
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )
        async with self._operation_lock:
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                custom_dns = await self._adapter.update_custom_dns(patch)
                settings = await self._adapter.get_settings()
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
            lambda: self._adapter.connect_country(normalized_code)
        )

    async def connect_country_with_features(
        self, country_code: str, features: list[str]
    ) -> None:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        normalized_features = normalize_server_features(features)
        if not normalized_features:
            await self._run_operation(
                lambda: self._adapter.connect_country(normalized_code)
            )
            return
        await self._run_operation(
            lambda: self._adapter.connect_country_with_features(
                normalized_code, normalized_features
            )
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
            )
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
                )
            )
            return
        await self._run_operation(
            lambda: self._adapter.connect_group_with_features(
                normalized_code,
                normalized_kind,
                normalized_name,
                normalized_features,
            )
        )

    async def connect_server(self, server_name: str) -> None:
        self._require_session()
        normalized_name = server_name.strip()
        if not normalized_name or len(normalized_name) > 128:
            raise UserVisibleValueError("Invalid Proton server name")
        await self._run_operation(lambda: self._adapter.connect_server(normalized_name))

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
        await self._run_operation(
            lambda: self._adapter.start_packet_capture(directory_path)
        )

    async def stop_packet_capture(self) -> None:
        self._require_session()
        await self._run_operation(self._adapter.stop_packet_capture)

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
        async with self._operation_lock:
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                await self._adapter.submit_support_report(report)
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
        await self._run_operation(
            lambda: self._adapter.login(normalized_username, password)
        )

    async def submit_two_factor(self, code: str) -> None:
        self._require_ready()
        normalized_code = code.strip()
        if len(normalized_code) not in {6, 8} or not normalized_code.isascii():
            raise UserVisibleValueError(
                "Enter a 6-digit code or an 8-character recovery code"
            )
        await self._run_operation(
            lambda: self._adapter.submit_two_factor(normalized_code)
        )

    async def cancel_login(self) -> None:
        self._require_ready()
        await self._run_operation(self._adapter.cancel_login)

    async def begin_fido2(self) -> None:
        self._require_ready()
        await self._run_operation(self._adapter.begin_fido2)

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
        await self._run_operation(self._adapter.logout)

    async def disable_kill_switch_for_login(self) -> None:
        if not self._snapshot.ready:
            raise UserVisibleRuntimeError("The Proton backend is not ready")
        if self._snapshot.logged_in:
            raise UserVisibleRuntimeError("The Proton account is already signed in")
        await self._run_operation(self._adapter.disable_kill_switch_for_login)

    async def disconnect(self) -> None:
        self._require_session()
        if self._operation_lock.locked():
            if self._snapshot.state != "connecting":
                raise UserVisibleRuntimeError(
                    "Another VPN operation is already in progress"
                )
            # Proton's connector accepts a Down event while an Up event is in
            # progress. Let that control operation bypass the serialization
            # lock so a slow or stalled connection can always be cancelled.
            await self._adapter.disconnect()
            return
        await self._run_operation(self._adapter.disconnect)

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        await self._adapter.set_reconnection_enabled(enabled)

    async def close(self) -> None:
        await self._adapter.close()

    def _require_session(self) -> None:
        self._require_ready()
        if not self._snapshot.logged_in:
            raise UserVisibleRuntimeError("A Proton account session is required")

    def _require_ready(self) -> None:
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

    async def _run_operation(self, operation: Callable[[], Awaitable[None]]) -> None:
        if self._operation_lock.locked():
            raise UserVisibleRuntimeError(
                "Another VPN operation is already in progress"
            )

        async with self._operation_lock:
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                await operation()
            except Exception:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message="The VPN operation could not be completed",
                    )
                )
                raise
            else:
                self._publish(replace(self._snapshot, busy=False))

    def _on_adapter_snapshot(self, snapshot: VpnSnapshot) -> None:
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
