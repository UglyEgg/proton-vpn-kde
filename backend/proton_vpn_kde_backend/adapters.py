# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Proton core and safe demo backend adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Coroutine
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, replace
from enum import Enum, auto
import logging
import os
from pathlib import Path
from typing import Any, Callable, NoReturn, TypeVar

from .async_utils import await_owned, join_owned, run_in_daemon_thread
from . import account_transition
from .account_transition import AccountTransitionJournal
from .task_scope import ScopeAdmissionExpired, TaskScope, create_owned_task
from .demo_adapter import DemoCoreAdapter
from .errors import (
    CleanupAdmissionExpired,
    ConnectorStartupError,
    NpsCompletionUnknownError,
    SessionExpiredError,
    UserVisibleRuntimeError,
    UserVisibleValueError,
    is_proton_authentication_needed,
)
from .controller import (
    CountryInfo,
    CustomDnsSettings,
    CustomDnsValue,
    LocationSearchInfo,
    NpsSurveyResponse,
    ProtocolInfo,
    ServerDataCallback,
    ServerGroupInfo,
    ServerInfo,
    ServerLoadInfo,
    SplitTunnelingSettings,
    SplitTunnelingValue,
    SettingsValue,
    SnapshotCallback,
    SupportReport,
    VpnSettings,
    VpnSnapshot,
)
from .core_compatibility import (
    cancellable_fido2_available as _cancellable_fido2_available,
    core_memory_optimization_behavior as _core_memory_optimization_behavior,
    core_memory_optimizations_active as _core_memory_optimizations_active,
    core_package_version as _core_package_version,
)
from .core_servers import (
    countries as core_countries,
    country as core_country,
    fastest_matching as core_fastest_matching,
    server_group as core_server_group,
    server_info as core_server_info,
)
from .core_settings import (
    custom_dns_from_core as translate_custom_dns,
    kill_switch_value as core_kill_switch_value,
    mode_value as core_mode_value,
    protocol_supports_split_tunneling as core_protocol_supports_split_tunneling,
    split_tunneling_from_core as translate_split_tunneling,
    vpn_settings_from_core as translate_vpn_settings,
)
from .core_snapshot import (
    SnapshotContext,
    snapshot_from_state as translate_snapshot,
    state_name as core_state_name,
)
from .core_protocols import (
    available_protocols as discover_protocols,
    iter_available_protocols as iter_core_protocols,
    protocol_supports_packet_capture as core_protocol_supports_packet_capture,
)
from .core_support import (
    submit_nps_survey as submit_core_nps_survey,
    submit_support_report as submit_core_support_report,
    take_pending_nps_survey as take_core_nps_survey,
)
from .fido_interaction import FidoInteraction
from .features import CRASH_REPORT_SUBMISSION_ENABLED, TELEMETRY_ENABLED
from .packet_capture import (
    PACKET_CAPTURE_MAX_SECONDS,
    PACKET_CAPTURE_STOP_ATTEMPT_SECONDS,
    PacketCaptureCoordinator,
)
from .reconnector import AsyncReconnector, ReconnectionRetirementTimeout
from .refresher_events import (
    RefreshFailure, RefreshFailureKind, RefresherFailureRelay, ignore_retired_refresh_error,
)
from .search_projection import ServerSearchProjection


__all__ = [
    "DemoCoreAdapter",
    "ProtonCoreAdapter",
    "_core_memory_optimization_behavior",
]


LOGOUT_RECOVERY_TIMEOUT_SECONDS = 5.0
CAPTURE_RECOVERY_SESSION_TIMEOUT_SECONDS = 5.0
CAPTURE_RECOVERY_CONNECTOR_TIMEOUT_SECONDS = 5.0
CONNECTION_RETIREMENT_SECONDS = 30.0
INCOMPLETE_CONNECTION_RETIREMENT_EXIT_CODE = 1
BACKGROUND_REFRESH_DEGRADED_MESSAGE = (
    "Some Proton background updates stopped. "
    "Sign out and sign in again to restart them."
)
_OwnedTaskResult = TypeVar("_OwnedTaskResult")


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _LogoutRecoveryOutcome:
    core_logged_in: bool | None
    protection_restored: bool
    session_recovery_failed: bool


@dataclass(frozen=True, slots=True)
class _ConnectionSupersession:
    reconnector: AsyncReconnector | None
    deadline: float


class _SessionServicesState(Enum):
    """Acknowledged scheduling state, not proof that Core children retired."""

    DISABLED = auto()
    ENABLED = auto()
    CLEANUP_REQUIRED = auto()


class ProtonCoreAdapter:
    """Thin adapter over the official python-proton-vpn-api-core package.

    Proton modules are imported lazily so demo mode and unit tests have no
    dependency on a locally installed Proton client.
    """

    def __init__(
        self,
        api: Any = None,
        *,
        packet_capture_max_seconds: float = PACKET_CAPTURE_MAX_SECONDS,
        packet_capture_stop_attempt_seconds: float = (
            PACKET_CAPTURE_STOP_ATTEMPT_SECONDS
        ),
        packet_capture_recovery_path: Path | None = None,
        crash_report_submission_enabled: bool = CRASH_REPORT_SUBMISSION_ENABLED,
        telemetry_enabled: bool = TELEMETRY_ENABLED,
        connection_retirement_seconds: float = CONNECTION_RETIREMENT_SECONDS,
        terminal_exit: Callable[[int], NoReturn] = os._exit,
        account_transition_path: Path | None = None,
    ):
        self._api: Any = api
        self._connector: Any = None
        self._callback: SnapshotCallback | None = None
        self._server_data_callback: ServerDataCallback | None = None
        self._initialized = False
        self._logged_in = False
        self._authentication_epoch = 0
        self._authentication_scope = TaskScope()
        self._reconnector: AsyncReconnector | None = None
        self._connection_scope = TaskScope()
        self._connection_intent_generation = 0
        self._manual_connection_tasks: dict[asyncio.Task[Any], int] = {}
        self._connector_state_revision = 0
        self._connector_state_changed = asyncio.Event()
        self._connection_retirement_seconds = max(
            0.0, connection_retirement_seconds
        )
        self._close_task: asyncio.Task[None] | None = None
        self._close_work_task: asyncio.Task[None] | None = None
        self._capture_stop_tasks: set[asyncio.Task[None]] = set()
        self._terminal_exit = terminal_exit
        self._reconnection_enabled = True
        self._status_message = ""
        self._auth_state = "signed_out"
        self._session_services_state = _SessionServicesState.DISABLED
        self._session_services_started = False
        self._background_refresh_degraded = False
        self._refresher_errors = RefresherFailureRelay(
            self._handle_refresher_failure, self._refresher_handler_failed
        )
        self._account_transition = AccountTransitionJournal(account_transition_path)
        self._account_restart_required = False
        self._fido_interaction: FidoInteraction | None = None
        self._crash_report_submission_enabled = crash_report_submission_enabled
        self._telemetry_enabled = telemetry_enabled
        self._packet_capture = PacketCaptureCoordinator(
            packet_capture_max_seconds,
            self._on_packet_capture_changed,
            packet_capture_stop_attempt_seconds,
            packet_capture_recovery_path,
        )
        self._kill_switch = 0
        self._startup_compatible = True
        self._server_list_generation = 0
        self._search_projection: ServerSearchProjection | None = None
        self._core_memory_optimized = False
        self._core_version = ""

    def has_pending_startup_recovery(self) -> bool:
        """Keep initialization alive while durable local cleanup is pending."""
        return (self._packet_capture.has_pending_recovery()
                or self._account_transition.exists())

    @property
    def _session_services_enabled(self) -> bool:
        """Compatibility view; lifecycle authority lives in the tri-state."""
        return self._session_services_state is _SessionServicesState.ENABLED

    async def initialize(
        self,
        callback: SnapshotCallback,
        server_data_callback: ServerDataCallback | None = None,
    ) -> VpnSnapshot:
        self._initialized = False
        self._callback = callback
        self._server_data_callback = server_data_callback
        self._core_memory_optimized = _core_memory_optimizations_active()
        self._core_version = _core_package_version()
        if self._api is None:
            from proton.vpn.core.api import ProtonVPNAPI
            from proton.vpn.core.session_holder import ClientTypeMetadata

            self._api = ProtonVPNAPI(ClientTypeMetadata(type="gui"))

        # Proton SSO reaches Secret Service through a synchronous keyring API.
        # Warm the cached session away from the D-Bus asyncio thread so a
        # provider unlock prompt (KeePassXC, KWallet, etc.) cannot freeze the
        # entire backend while waiting for user approval. Core also restores
        # this session while constructing its connector, so recovery cannot
        # safely acquire the connection first. When a capture or account
        # recovery record exists, bound the prewarm: an unanswered prompt must fail startup
        # nonzero with the record retained for systemd retry.
        pending_capture_recovery = self._packet_capture.has_pending_recovery()
        pending_account_transition = self._account_transition.load()
        if pending_account_transition is not None:
            self._account_restart_required = True
            if pending_account_transition.process_generation == account_transition.PROCESS_GENERATION:
                raise UserVisibleRuntimeError(
                    "Account replacement requires a new backend process"
                )
            if not account_transition.retired_process_confirmed(pending_account_transition):
                raise UserVisibleRuntimeError(
                    "The outgoing backend is still stopping; retry the service shortly"
                )
        pending_cleanup = pending_capture_recovery or pending_account_transition is not None
        session_probe = run_in_daemon_thread(self._api.is_user_logged_in)
        if pending_cleanup:
            try:
                self._logged_in = await asyncio.wait_for(
                    session_probe,
                    timeout=CAPTURE_RECOVERY_SESSION_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                raise UserVisibleRuntimeError(
                    "Proton session restoration did not finish while "
                    "local cleanup was pending"
                ) from None
        else:
            self._logged_in = await session_probe

        if pending_capture_recovery and not self._logged_in:
            # Core intentionally ignores a persisted connection while logged
            # out and reports a synthetic disconnected connector. That state
            # cannot prove an external capture stopped, so retain the journal
            # and fail startup for systemd retry instead of clearing it.
            raise UserVisibleRuntimeError(
                "Proton session restoration is required to recover an "
                "unconfirmed packet capture"
            )

        connector_request = self._api.get_vpn_connector()
        if pending_cleanup:
            try:
                self._connector = await asyncio.wait_for(
                    connector_request,
                    timeout=CAPTURE_RECOVERY_CONNECTOR_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                raise UserVisibleRuntimeError(
                    "Proton Core did not restore the VPN connection while "
                    "local cleanup was pending"
                ) from None
        else:
            try:
                self._connector = await connector_request
            except Exception as error:
                # Session restoration already completed. Do not misrepresent
                # a NetworkManager/connector failure as rejected credentials.
                raise ConnectorStartupError(logged_in=self._logged_in) from error
        self._connector.register(self)
        # Packet capture is external to this process. Reacquire any durable
        # completion-unknown generation before backend-readiness publication.
        await self._packet_capture.recover(self._connector)
        if pending_account_transition is not None:
            if not self._logged_in and not pending_account_transition.tunnel_retired:
                # Core deliberately cannot restore a persisted tunnel without
                # a session. Its synthetic Disconnected is not teardown proof.
                raise UserVisibleRuntimeError(
                    "The previous account's tunnel cleanup is unconfirmed; "
                    "account recovery requires operator assistance"
                )
            # No refresher has been enabled in this process. Clear any saved
            # session resurrected by an outgoing refresh before publishing
            # readiness or accepting replacement credentials.
            async with self._serialized_authentication_transition():
                async with self._serialized_connection_lifecycle():
                    cleanup = self._create_owned_child_task(
                        self._finish_account_restart(),
                        authentication=True,
                        connection=True,
                    )
                    _, pending = await asyncio.wait(
                        {cleanup}, timeout=self._connection_retirement_seconds
                    )
                    if pending:
                        self._terminate_failed_connection_retirement("account recovery", 1)
                    cleanup.result()
        self._auth_state = "signed_in" if self._logged_in else "signed_out"
        validator = getattr(self._api, "validate_connection_availability", None)
        if callable(validator):
            self._startup_compatible = bool(validator())
        else:
            # API-core 5.5.6 as initially shipped on Fedora lacks the public
            # validator used by GUI v4.18.0. Its connector protocol registry is
            # the closest public compatibility check and avoids private core
            # internals until distributions pick up the helper.
            self._startup_compatible = any(self._iter_available_protocols())
        self._api.refresher.set_server_list_updated_callback(
            self._on_server_list_updated
        )
        self._api.refresher.set_server_loads_updated_callback(
            self._on_server_loads_updated
        )
        location_callback_setter = getattr(
            self._api.refresher, "set_location_names_updated_callback", None
        )
        if callable(location_callback_setter):
            location_callback_setter(self._on_location_names_updated)

        if not self._logged_in:
            try:
                settings = await self._load_settings()
            except Exception:
                self._kill_switch = 0
                self._auth_state = "settings_unavailable"
                self._status_message = (
                    "Proton could not read the kill switch setting; restart the "
                    "backend before signing in"
                )
            else:
                self._kill_switch = self._kill_switch_value(settings)

        async with self._serialized_authentication_transition():
            if self._logged_in:
                await self._enable_session_services()

        snapshot = self._snapshot_from_state(self._connector.current_state)
        # Connector, capture-recovery, and refresher callbacks may run while
        # Core is still initializing. Keep their state updates internal until
        # the controller receives this single authoritative ready snapshot.
        self._initialized = True
        return snapshot

    async def _finish_account_restart(self) -> None:
        await self._logout_with_disconnect_barrier(self._connection_retirement_deadline())
        if await run_in_daemon_thread(self._api.is_user_logged_in):
            raise UserVisibleRuntimeError("The outgoing Proton account could not be cleared")
        self._account_transition.clear()
        self._account_restart_required = False
        self._logged_in = False

    async def connect_fastest(self) -> None:
        async with self._manual_connection_target() as (
            authentication_epoch,
            connection_intent,
        ):
            server_list = await self._get_server_list(authentication_epoch)
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            logical_server = server_list.get_fastest()
            await self._connect_logical(
                logical_server, authentication_epoch, connection_intent
            )

    async def connect_fastest_with_feature(self, feature: str) -> None:
        await self.connect_fastest_with_features((feature,))

    async def connect_fastest_with_features(self, features: tuple[str, ...]) -> None:
        async with self._manual_connection_target() as (
            authentication_epoch,
            connection_intent,
        ):
            server_list = await self._get_server_list(authentication_epoch)
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            logical_server = self._fastest_matching(
                server_list, server_list.logicals, features
            )
            await self._connect_logical(
                logical_server, authentication_epoch, connection_intent
            )

    @staticmethod
    def _fastest_matching(server_list, servers, features: tuple[str, ...]):
        return core_fastest_matching(server_list, servers, features)

    async def get_countries(self) -> list[CountryInfo]:
        authentication_epoch = self._authenticated_epoch()
        server_list = await self._get_server_list(authentication_epoch)
        countries = []
        for country in self._countries(server_list):
            available = list(
                server_list.get_available_servers(
                    country.servers, server_list.user_tier
                )
            )
            countries.append(
                CountryInfo(
                    code=country.code.upper(),
                    server_count=len(country.servers),
                    accessible=bool(available),
                    under_maintenance=bool(
                        getattr(country, "under_maintenance", False)
                    ),
                    free=bool(getattr(country, "free", False)),
                )
            )
        self._require_authenticated_epoch(authentication_epoch)
        return countries

    async def get_server_groups(self, country_code: str) -> list[ServerGroupInfo]:
        from proton.vpn.session.servers import ServerFeatureEnum

        authentication_epoch = self._authenticated_epoch()
        server_list = await self._get_server_list(authentication_epoch)
        country = self._country(server_list, country_code)
        groups = [("location", location) for location in country.locations]
        if country.secure_core_group is not None:
            groups.append(("secure-core", country.secure_core_group))

        result = []
        for kind, group in groups:
            available = list(
                server_list.get_available_servers(group.servers, server_list.user_tier)
            )
            result.append(
                ServerGroupInfo(
                    kind=kind,
                    name=group.name,
                    server_count=len(group.servers),
                    accessible=bool(available),
                    under_maintenance=group.under_maintenance,
                    smart_routing=group.smart_routing,
                    secure_core=ServerFeatureEnum.SECURE_CORE in group.features,
                    tor=ServerFeatureEnum.TOR in group.features,
                    p2p=ServerFeatureEnum.P2P in group.features,
                    streaming=ServerFeatureEnum.STREAMING in group.features,
                )
            )
        self._require_authenticated_epoch(authentication_epoch)
        return result

    async def get_group_servers(
        self, country_code: str, group_kind: str, group_name: str
    ) -> list[ServerInfo]:
        authentication_epoch = self._authenticated_epoch()
        server_list = await self._get_server_list(authentication_epoch)
        group = self._server_group(server_list, country_code, group_kind, group_name)
        servers = [self._server_info(server_list, server) for server in group.servers]
        result = sorted(
            servers,
            key=lambda item: (
                not item.accessible,
                item.under_maintenance,
                item.load,
                item.name,
            ),
        )
        self._require_authenticated_epoch(authentication_epoch)
        return result

    async def get_server_loads(self, country_code: str) -> list[ServerLoadInfo]:
        authentication_epoch = self._authenticated_epoch()
        server_list = await self._get_server_list(authentication_epoch)
        result = [
            ServerLoadInfo(server.name, server.load or 0)
            for server in server_list.logicals
            if server.exit_country.upper() == country_code
        ]
        self._require_authenticated_epoch(authentication_epoch)
        return result

    async def search_locations(self, query: str) -> list[LocationSearchInfo]:
        from proton.vpn.session.servers import ServerFeatureEnum
        from proton.vpn.session.servers.logicals import (
            sort_servers_alphabetically_by_country_and_server_name,
        )

        authentication_epoch = self._authenticated_epoch()
        server_list = await self._get_server_list(authentication_epoch)
        if (
            self._search_projection is None
            or self._search_projection.generation != self._server_list_generation
        ):
            projection = ServerSearchProjection.build(
                server_list,
                self._server_list_generation,
                ServerFeatureEnum.SECURE_CORE,
                sort_servers_alphabetically_by_country_and_server_name,
            )
            # Building is synchronous, but assignment is an adapter-owned
            # state commit.  Never let a successful request from a retired
            # account poison the replacement account's search cache.
            self._require_authenticated_epoch(authentication_epoch)
            self._search_projection = projection
        self._require_authenticated_epoch(authentication_epoch)
        return self._search_projection.search(server_list, query)

    async def get_settings(self) -> VpnSettings:
        authentication_epoch = self._authenticated_epoch()
        settings = await self._load_settings(authentication_epoch)
        return self._settings_from_core(settings)

    async def get_split_tunneling(self) -> SplitTunnelingSettings:
        authentication_epoch = self._authenticated_epoch()
        settings = await self._load_settings(authentication_epoch)
        return self._split_tunneling_from_core(settings)

    async def get_custom_dns(self) -> CustomDnsSettings:
        authentication_epoch = self._authenticated_epoch()
        settings = await self._load_settings(authentication_epoch)
        return self._custom_dns_from_core(settings)

    async def update_settings(self, patch: dict[str, SettingsValue]) -> VpnSettings:
        authentication_epoch = self._authenticated_epoch()
        if (
            patch.get("anonymousCrashReports") is True
            and not self._crash_report_submission_enabled
        ):
            raise UserVisibleRuntimeError(
                "Anonymous crash reporting is disabled in this unofficial community build"
            )
        if patch.get("telemetry") is True and not self._telemetry_enabled:
            raise UserVisibleRuntimeError(
                "Connection telemetry is disabled in this community build"
            )
        settings = await self._load_settings(authentication_epoch)
        if "telemetry" in patch and not hasattr(settings, "telemetry"):
            raise UserVisibleRuntimeError(
                "Connection telemetry is unavailable with the installed Proton Core"
            )
        state_name = type(self._connector.current_state).__name__.lower()
        if state_name != "disconnected" and ({"protocol", "killSwitch"} & set(patch)):
            raise UserVisibleRuntimeError(
                "Disconnect the VPN before changing protocol or kill switch"
            )

        paid_fields = {
            "netShield",
            "vpnAccelerator",
            "moderateNat",
            "portForwarding",
        }
        if self._user_tier() < 1 and paid_fields & set(patch):
            raise UserVisibleRuntimeError(
                "This setting requires a paid Proton VPN plan"
            )

        protocols = {item.id for item in self._available_protocols(settings.protocol)}
        requested_protocol = patch.get("protocol")
        if requested_protocol is not None:
            if (
                not isinstance(requested_protocol, str)
                or requested_protocol not in protocols
            ):
                raise UserVisibleValueError("Select an available VPN protocol")

        split_tunneling_enabled = bool(settings.features.split_tunneling.enabled)
        if (
            split_tunneling_enabled
            and patch.get("killSwitch", settings.killswitch) != 0
        ):
            raise UserVisibleValueError(
                "Disable split tunneling before enabling the kill switch"
            )
        if (
            split_tunneling_enabled
            and requested_protocol is not None
            and not self._protocol_supports_split_tunneling(requested_protocol)
        ):
            raise UserVisibleValueError(
                "Disable split tunneling before selecting this protocol"
            )
        if (
            bool(settings.custom_dns.enabled)
            and patch.get("netShield", settings.features.netshield) != 0
        ):
            raise UserVisibleValueError("Disable custom DNS before enabling NetShield")

        previous_values = (
            settings.protocol,
            settings.killswitch,
            settings.features.netshield,
            settings.features.vpn_accelerator,
            settings.features.moderate_nat,
            settings.features.port_forwarding,
            settings.ipv6,
            settings.anonymous_crash_reports,
            getattr(settings, "telemetry", None),
        )

        def rollback() -> None:
            (
                settings.protocol,
                settings.killswitch,
                settings.features.netshield,
                settings.features.vpn_accelerator,
                settings.features.moderate_nat,
                settings.features.port_forwarding,
                settings.ipv6,
                settings.anonymous_crash_reports,
                previous_telemetry,
            ) = previous_values
            if previous_telemetry is not None:
                settings.telemetry = previous_telemetry

        for key, value in patch.items():
            if key == "protocol":
                settings.protocol = value
            elif key == "killSwitch":
                settings.killswitch = value
            elif key == "netShield":
                settings.features.netshield = value
            elif key == "vpnAccelerator":
                settings.features.vpn_accelerator = value
            elif key == "moderateNat":
                settings.features.moderate_nat = value
            elif key == "portForwarding":
                settings.features.port_forwarding = value
            elif key == "ipv6":
                settings.ipv6 = value
            elif key == "anonymousCrashReports":
                settings.anonymous_crash_reports = value
            elif key == "telemetry":
                settings.telemetry = value

        self._require_authenticated_epoch(authentication_epoch)
        await self._save_settings_transactionally(
            settings,
            rollback,
            protection_sensitive="killSwitch" in patch,
            authentication_epoch=authentication_epoch,
            telemetry_explicit="telemetry" in patch,
        )
        self._kill_switch = self._kill_switch_value(settings)
        return self._settings_from_core(settings)

    async def update_split_tunneling(
        self, patch: dict[str, SplitTunnelingValue]
    ) -> SplitTunnelingSettings:
        authentication_epoch = self._authenticated_epoch()
        settings = await self._load_settings(authentication_epoch)
        split_tunneling = settings.features.split_tunneling
        if not bool(self._connector.is_split_tunneling_available):
            raise UserVisibleRuntimeError(
                "Split tunneling is unavailable on this system"
            )
        if self._user_tier() < 1:
            raise UserVisibleRuntimeError(
                "Split tunneling requires a paid Proton VPN plan"
            )

        previous_values = (
            split_tunneling.mode,
            bool(split_tunneling.enabled),
            list(split_tunneling.exclude.app_paths),
            list(split_tunneling.include.app_paths),
            list(split_tunneling.exclude.ip_ranges),
            list(split_tunneling.include.ip_ranges),
        )

        def rollback() -> None:
            split_tunneling.mode = previous_values[0]
            split_tunneling.enabled = previous_values[1]
            split_tunneling.exclude.app_paths = list(previous_values[2])
            split_tunneling.include.app_paths = list(previous_values[3])
            split_tunneling.exclude.ip_ranges = list(previous_values[4])
            split_tunneling.include.ip_ranges = list(previous_values[5])

        final_enabled = patch.get("enabled", split_tunneling.enabled)
        final_mode = patch.get("mode", self._mode_value(split_tunneling.mode))
        if final_enabled:
            if int(settings.killswitch) != 0:
                raise UserVisibleValueError(
                    "Disable the kill switch before enabling split tunneling"
                )
            if not self._protocol_supports_split_tunneling(settings.protocol):
                raise UserVisibleValueError(
                    "Select WireGuard or a compatible protocol first"
                )
            if final_mode == "include":
                include_paths = patch.get(
                    "includeAppPaths", split_tunneling.include.app_paths
                )
                include_ranges = patch.get(
                    "includeIpRanges", split_tunneling.include.ip_ranges
                )
                if not include_paths and not include_ranges:
                    raise UserVisibleValueError(
                        "Select at least one included application or IP range before enabling this mode"
                    )

        if "mode" in patch:
            from proton.vpn.core.settings.split_tunneling import SplitTunnelingMode

            split_tunneling.mode = SplitTunnelingMode(patch["mode"])
        if "excludeAppPaths" in patch:
            value = patch["excludeAppPaths"]
            if not isinstance(value, list):
                raise UserVisibleValueError("The excluded applications are invalid")
            split_tunneling.exclude.app_paths = list(value)
        if "includeAppPaths" in patch:
            value = patch["includeAppPaths"]
            if not isinstance(value, list):
                raise UserVisibleValueError("The included applications are invalid")
            split_tunneling.include.app_paths = list(value)
        if "excludeIpRanges" in patch:
            value = patch["excludeIpRanges"]
            if not isinstance(value, list):
                raise UserVisibleValueError("The excluded IP ranges are invalid")
            split_tunneling.exclude.ip_ranges = list(value)
        if "includeIpRanges" in patch:
            value = patch["includeIpRanges"]
            if not isinstance(value, list):
                raise UserVisibleValueError("The included IP ranges are invalid")
            split_tunneling.include.ip_ranges = list(value)
        if "enabled" in patch:
            split_tunneling.enabled = bool(patch["enabled"])

        self._require_authenticated_epoch(authentication_epoch)
        await self._save_settings_transactionally(
            settings, rollback, authentication_epoch=authentication_epoch
        )
        return self._split_tunneling_from_core(settings)

    async def update_custom_dns(
        self, patch: dict[str, CustomDnsValue]
    ) -> CustomDnsSettings:
        authentication_epoch = self._authenticated_epoch()
        settings = await self._load_settings(authentication_epoch)
        if self._user_tier() < 1:
            raise UserVisibleRuntimeError("Custom DNS requires a paid Proton VPN plan")

        previous_enabled = bool(settings.custom_dns.enabled)
        previous_servers = list(settings.custom_dns.ip_list)

        def rollback() -> None:
            settings.custom_dns.enabled = previous_enabled
            settings.custom_dns.ip_list = list(previous_servers)

        final_enabled = patch.get("enabled", settings.custom_dns.enabled)
        if final_enabled and int(settings.features.netshield) != 0:
            raise UserVisibleValueError("Disable NetShield before enabling custom DNS")

        if "servers" in patch:
            from proton.vpn.core.settings import CustomDNSEntry

            server_values = patch["servers"]
            if not isinstance(server_values, list):
                raise UserVisibleValueError("The custom-DNS servers are invalid")
            settings.custom_dns.ip_list = [
                CustomDNSEntry.new_from_string(
                    str(server["address"]),
                    enabled=bool(server["enabled"]),
                )
                for server in server_values
                if isinstance(server, dict)
            ]
        if "enabled" in patch:
            settings.custom_dns.enabled = bool(patch["enabled"])

        self._require_authenticated_epoch(authentication_epoch)
        await self._save_settings_transactionally(
            settings, rollback, authentication_epoch=authentication_epoch
        )
        return self._custom_dns_from_core(settings)

    async def _load_settings(self, authentication_epoch: int | None = None):
        request_epoch = (
            self._authentication_epoch
            if authentication_epoch is None
            else authentication_epoch
        )
        try:
            settings = await self._api.load_settings()
        except Exception as error:
            if is_proton_authentication_needed(error):
                await self._raise_session_error(error, request_epoch)
            raise UserVisibleRuntimeError(
                "Proton could not load the VPN settings"
            ) from None
        self._require_authentication_epoch(request_epoch)
        if not self._crash_report_submission_enabled:
            # Core's public load_settings method mirrors the persisted value
            # into UsageReporting before it returns. Reads remain free of
            # persistence writes, while the unsupported sender stays disabled
            # for the lifetime of this process.
            usage_reporting = getattr(self._api, "usage_reporting", None)
            if usage_reporting is not None:
                usage_reporting.enabled = False
        self._apply_telemetry_policy(settings)
        return settings

    def _apply_telemetry_policy(
        self, settings: Any, *, explicit_preference: bool = False
    ) -> None:
        """Keep optional Core telemetry off unless this client opts in."""
        if not hasattr(settings, "telemetry"):
            return

        if self._telemetry_enabled and explicit_preference:
            return
        if self._telemetry_enabled:
            persistence = getattr(self._api, "_settings_persistence", None)
            if getattr(persistence, "_settings_are_default", False) is False:
                return

        # Core 5.7 mirrors the stored value into its event queue while loading
        # settings. A community build always disables it. A telemetry-capable
        # build also projects a fresh Core profile as off until the first
        # explicit settings write; existing persisted Proton preferences remain
        # authoritative. Mutating this detached copy does not persist it.
        settings.telemetry = False
        telemetry_events = getattr(self._api, "_telemetry_events", None)
        enable = getattr(telemetry_events, "enable", None)
        if callable(enable):
            enable(False)

    async def _save_settings(
        self,
        settings: Any,
        authentication_epoch: int | None = None,
        *,
        telemetry_explicit: bool = False,
    ) -> None:
        request_epoch = (
            self._authentication_epoch
            if authentication_epoch is None
            else authentication_epoch
        )
        self._require_authentication_epoch(request_epoch)
        if not self._crash_report_submission_enabled:
            # Settings writes are explicit mutations, so they are the safe
            # place to persist this community build's disabled-reporting
            # policy. Pure reads never write the whole Core settings object.
            settings.anonymous_crash_reports = False
        self._apply_telemetry_policy(
            settings, explicit_preference=telemetry_explicit
        )
        try:
            await self._api.save_settings(settings)
        except Exception as error:
            if is_proton_authentication_needed(error):
                await self._raise_session_error(error, request_epoch)
            raise UserVisibleRuntimeError(
                "Proton could not save the VPN settings"
            ) from None
        self._require_authentication_epoch(request_epoch)

    async def _save_settings_transactionally(
        self,
        settings: Any,
        rollback: Callable[[], None],
        *,
        protection_sensitive: bool = False,
        authentication_epoch: int | None = None,
        telemetry_explicit: bool = False,
    ) -> None:
        async with self._serialized_authentication_transition():
            await self._save_settings_transactionally_with_authentication_barrier(
                settings,
                rollback,
                protection_sensitive=protection_sensitive,
                authentication_epoch=authentication_epoch,
                telemetry_explicit=telemetry_explicit,
            )

    async def _save_settings_transactionally_with_authentication_barrier(
        self,
        settings: Any,
        rollback: Callable[[], None],
        *,
        protection_sensitive: bool,
        authentication_epoch: int | None,
        telemetry_explicit: bool,
    ) -> None:
        """Compensate a user setting write whose commit status is ambiguous."""

        save_task = self._create_owned_child_task(
            self._save_settings(
                settings,
                authentication_epoch,
                telemetry_explicit=telemetry_explicit,
            ),
            authentication=True,
        )
        original_error: BaseException | None = None
        cancellation_requested = False
        try:
            await asyncio.wait((save_task,))
            save_task.result()
            return
        except SessionExpiredError:
            # Authentication expiry owns the recovery path. Core may have
            # persisted the requested value before discovering the expired
            # session, but another authenticated write cannot safely be used
            # as compensation. Restore the local object and let the next
            # sign-in reload the authoritative persisted settings.
            rollback()
            raise
        except asyncio.CancelledError as error:
            original_error = error
            cancellation_requested = True
        except Exception as error:
            original_error = error

        recovery_task = self._create_owned_child_task(
            self._recover_failed_settings_save(
                settings,
                rollback,
                save_task,
                protection_sensitive=protection_sensitive,
                authentication_epoch=authentication_epoch,
                telemetry_explicit=telemetry_explicit,
            ),
            authentication=True,
        )
        while not recovery_task.done():
            try:
                await asyncio.wait((recovery_task,))
            except asyncio.CancelledError:
                cancellation_requested = True
        try:
            recovered = recovery_task.result()
        except SessionExpiredError:
            if cancellation_requested:
                raise asyncio.CancelledError() from None
            raise

        if cancellation_requested:
            raise asyncio.CancelledError() from None
        if not recovered:
            raise UserVisibleRuntimeError(
                "Proton could not confirm the VPN settings after a failed save; "
                "restart the backend and review VPN settings before continuing"
            ) from None
        assert original_error is not None
        raise original_error

    async def _recover_failed_settings_save(
        self,
        settings: Any,
        rollback: Callable[[], None],
        save_task: asyncio.Task[None],
        *,
        protection_sensitive: bool,
        authentication_epoch: int | None,
        telemetry_explicit: bool,
    ) -> bool:
        completed, _ = await asyncio.wait(
            (save_task,), timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS
        )
        try:
            # A stage timeout is not retirement of Core's executor-backed
            # write. Keep its authentication owner until it is terminal; the
            # enclosing foreground deadline remains the process backstop.
            await await_owned(save_task)
        except SessionExpiredError:
            rollback()
            raise
        except (Exception, asyncio.CancelledError):
            # A failed acknowledgement can follow a completed persistence
            # write, so compensation is still mandatory.
            pass

        if not completed:
            await self._publish_unknown_settings(protection_sensitive)
            return False

        rollback()
        try:
            async with asyncio.timeout(LOGOUT_RECOVERY_TIMEOUT_SECONDS):
                outcome = await join_owned(self._create_owned_child_task(
                    self._save_settings(
                        settings,
                        authentication_epoch,
                        telemetry_explicit=telemetry_explicit,
                    ),
                    authentication=True,
                ))
                # Expiry reconciled by the write's owner stays authoritative
                # even when the acknowledgement crossed this stage's timer.
                if isinstance(outcome.error, SessionExpiredError):
                    raise outcome.error
                outcome.result()
        except SessionExpiredError:
            raise
        except (Exception, asyncio.CancelledError):
            await self._publish_unknown_settings(protection_sensitive)
            return False
        return True

    async def _publish_unknown_settings(self, protection_sensitive: bool) -> None:
        await self._quiesce_session_services()
        self._logged_in = False
        self._search_projection = None
        if protection_sensitive:
            # Persistence is ambiguous, so never claim permanent protection.
            self._kill_switch = 0
            self._auth_state = "protection_unknown"
            self._status_message = (
                "Proton could not confirm the kill switch setting after a "
                "failed save; restart the backend and review VPN settings "
                "before reconnecting"
            )
        else:
            self._auth_state = "settings_unavailable"
            self._status_message = (
                "Proton could not confirm VPN settings after a failed save; "
                "restart the backend and review VPN settings before continuing"
            )
        self._publish_snapshot()

    async def connect_country(self, country_code: str) -> None:
        async with self._manual_connection_target() as (
            authentication_epoch,
            connection_intent,
        ):
            server_list = await self._get_server_list(authentication_epoch)
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            await self._connect_logical(
                server_list.get_fastest_in_country(country_code),
                authentication_epoch,
                connection_intent,
            )

    async def connect_country_with_features(
        self, country_code: str, features: tuple[str, ...]
    ) -> None:
        async with self._manual_connection_target() as (
            authentication_epoch,
            connection_intent,
        ):
            server_list = await self._get_server_list(authentication_epoch)
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            country = self._country(server_list, country_code)
            logical_server = self._fastest_matching(
                server_list, country.servers, features
            )
            await self._connect_logical(
                logical_server, authentication_epoch, connection_intent
            )

    async def connect_group(
        self, country_code: str, group_kind: str, group_name: str
    ) -> None:
        async with self._manual_connection_target() as (
            authentication_epoch,
            connection_intent,
        ):
            server_list = await self._get_server_list(authentication_epoch)
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            group = self._server_group(
                server_list, country_code, group_kind, group_name
            )
            available = server_list.get_available_servers(
                group.servers, server_list.user_tier
            )
            logical_server = server_list.get_fastest_server(available)
            if logical_server is None:
                raise UserVisibleRuntimeError(
                    "No server available in the current tier"
                )
            await self._connect_logical(
                logical_server, authentication_epoch, connection_intent
            )

    async def connect_group_with_features(
        self,
        country_code: str,
        group_kind: str,
        group_name: str,
        features: tuple[str, ...],
    ) -> None:
        async with self._manual_connection_target() as (
            authentication_epoch,
            connection_intent,
        ):
            server_list = await self._get_server_list(authentication_epoch)
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            group = self._server_group(
                server_list, country_code, group_kind, group_name
            )
            logical_server = self._fastest_matching(
                server_list, group.servers, features
            )
            await self._connect_logical(
                logical_server, authentication_epoch, connection_intent
            )

    async def connect_server(self, server_name: str) -> None:
        async with self._manual_connection_target() as (
            authentication_epoch,
            connection_intent,
        ):
            server_list = await self._get_server_list(authentication_epoch)
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            await self._connect_logical(
                server_list.get_by_name(server_name),
                authentication_epoch,
                connection_intent,
            )

    async def start_packet_capture(self, directory_path: str) -> None:
        # Capture start creates durable, account-owned Core state. Serialize
        # it with every authentication transition so expiry or account
        # replacement cannot overtake a successful start and misattribute it.
        async with self._serialized_authentication_transition():
            authentication_epoch = self._authenticated_epoch()
            await self._packet_capture.start(self._connector, directory_path)
            self._require_authenticated_epoch(authentication_epoch)

    async def stop_packet_capture(self, *, deadline: float | None = None) -> None:
        if deadline is None:
            deadline = self._connection_retirement_deadline()
        self._require_cleanup_dispatch_time(deadline)
        await await_owned(self._stop_packet_capture_before_deadline(deadline))

    async def _stop_packet_capture_before_deadline(self, deadline: float) -> None:
        self._require_cleanup_dispatch_time(deadline)
        pending_stop = self._packet_capture.stop(deadline=deadline)
        try:
            task = asyncio.create_task(pending_stop)
        except BaseException:
            pending_stop.close()
            raise
        self._capture_stop_tasks.add(task)
        task.add_done_callback(self._retire_capture_stop)
        _, pending = await asyncio.wait(
            {task}, timeout=max(0.0, deadline - asyncio.get_running_loop().time())
        )
        if pending:
            # The durable capture journal remains authoritative on restart.
            # Never drop a live Stop owner or race it with replacement work.
            self._terminate_failed_connection_retirement("packet capture stop", len(pending))
        task.result()

    def _retire_capture_stop(self, task: asyncio.Task[None]) -> None:
        self._capture_stop_tasks.discard(task)
        if not task.cancelled():
            task.exception()

    @staticmethod
    def _require_cleanup_dispatch_time(deadline: float) -> None:
        if asyncio.get_running_loop().time() >= deadline:
            raise CleanupAdmissionExpired()

    def _cancel_packet_capture_watchdog(self) -> None:
        self._packet_capture.cancel_watchdog()

    def _finish_packet_capture_state(self) -> None:
        self._packet_capture.finish()

    @property
    def _packet_capture_active(self) -> bool:
        return self._packet_capture.active

    @property
    def _packet_capture_watchdog_task(self) -> asyncio.Task | None:
        return self._packet_capture.watchdog_task

    def _on_packet_capture_changed(self, message: str | None) -> None:
        if message is not None:
            self._status_message = message
        self._publish_snapshot()

    async def submit_support_report(self, report: SupportReport) -> None:
        async with self._serialized_authentication_transition():
            authentication_epoch = self._authenticated_epoch()
            try:
                await submit_core_support_report(self._api, report)
            except Exception as error:
                await self._raise_session_error(error, authentication_epoch)
            self._require_authenticated_epoch(authentication_epoch)

    async def take_pending_nps_survey(self) -> bool:
        async with self._serialized_authentication_transition():
            authentication_epoch = self._authenticated_epoch()
            try:
                available = await take_core_nps_survey(self._api)
            except Exception as error:
                await self._raise_session_error(error, authentication_epoch)
            self._require_authenticated_epoch(authentication_epoch)
            return available

    async def submit_nps_survey(self, response: NpsSurveyResponse) -> None:
        async with self._serialized_authentication_transition():
            authentication_epoch = self._authenticated_epoch()
            try:
                await submit_core_nps_survey(self._api, response)
            except Exception as error:
                if is_proton_authentication_needed(error):
                    try:
                        await self._raise_session_error(error, authentication_epoch)
                    except SessionExpiredError:
                        # Survey submission is completion-unknown even when its
                        # authentication failure authoritatively expires the
                        # owning session.
                        raise NpsCompletionUnknownError(
                            "Survey submission completion could not be confirmed"
                        ) from None
                raise
            self._require_authenticated_epoch(authentication_epoch)

    async def _get_server_list(self, authentication_epoch: int):
        try:
            server_list = await self._api.refresher.get_up_to_date_server_list()
        except Exception as error:
            await self._raise_session_error(error, authentication_epoch)
        self._require_authenticated_epoch(authentication_epoch)
        return server_list

    @staticmethod
    def _countries(server_list):
        return core_countries(server_list)

    def _country(self, server_list, country_code: str):
        return core_country(server_list, country_code)

    def _server_group(
        self, server_list, country_code: str, group_kind: str, group_name: str
    ):
        return core_server_group(
            server_list, country_code, group_kind, group_name
        )

    @staticmethod
    def _server_info(server_list, server) -> ServerInfo:
        return core_server_info(server_list, server)

    async def _connect_logical(
        self,
        logical_server,
        authentication_epoch: int,
        connection_intent: int,
    ) -> None:
        if not self._manual_connection_is_current(
            authentication_epoch, connection_intent
        ):
            return
        # The public route owns retry suspension from admission through this
        # complete Core operation; this helper must not create a second owner.
        try:
            client_config = (
                await self._api.refresher.get_up_to_date_client_config()
            )
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            vpn_server = self._connector.get_vpn_server(
                logical_server, client_config
            )
            settings = await self._load_settings(authentication_epoch)
            if not self._manual_connection_is_current(
                authentication_epoch, connection_intent
            ):
                return
            await self._attempt_connection(
                lambda: self._connector.connect(
                    vpn_server, protocol=settings.protocol
                ),
                authentication_epoch,
                connection_intent,
            )
        except Exception as error:
            await self._raise_session_error(error, authentication_epoch)

    async def _attempt_reconnection(
        self,
        vpn_server: Any,
        protocol: Any,
        backend: Any,
        authentication_epoch: int,
    ) -> bool:
        return await self._attempt_connection(
            lambda: self._connector.connect(vpn_server, protocol, backend),
            authentication_epoch,
            self._connection_intent_generation,
        )

    async def _attempt_connection(
        self,
        operation: Callable[[], Awaitable[None]],
        authentication_epoch: int,
        connection_intent: int,
    ) -> bool:
        """Own one Core connection side effect and retire stale success."""
        async with self._serialized_connection_lifecycle():
            if connection_intent != self._connection_intent_generation:
                return False
            self._require_authenticated_epoch(authentication_epoch)
            try:
                # Core 5.6.10 through 5.6.20 can await a NetworkManager future
                # in an executor here. Cancelling only the asyncio caller would
                # detach that worker and allow an obsolete generation to add a
                # profile later. Retain the provider coroutine until its worker
                # and Core's own late-cancellation cleanup are both terminal.
                await await_owned(operation())
            except asyncio.CancelledError:
                # Connect completion is unknown after cancellation.  Remain
                # the lifecycle owner until a compensating Down completes.
                await self._disconnect_until_stable()
                raise

            current_task = asyncio.current_task()
            if current_task is not None and current_task.cancelling():
                # A provider may suppress cancellation and return success.
                # Preserve the caller's cancellation only after retiring that
                # completion-unknown connection.
                await self._disconnect_until_stable()
                raise asyncio.CancelledError

            authentication_current = (
                authentication_epoch == self._authentication_epoch
                and self._logged_in
            )
            intent_current = (
                connection_intent == self._connection_intent_generation
            )
            if authentication_current and intent_current:
                return True

            # Expiry, explicit Disconnect, Logout, shutdown, or a newer manual
            # target retired this successful attempt while Core was awaiting.
            await self._disconnect_until_stable()
            if not authentication_current:
                raise SessionExpiredError(
                    "The Proton account session changed"
                ) from None
            return False

    def _advance_connection_intent(self) -> int:
        self._connection_intent_generation += 1
        return self._connection_intent_generation

    @asynccontextmanager
    async def _manual_connection_target(self) -> AsyncIterator[tuple[int, int]]:
        """Own and retire every older target before manual work can proceed."""
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("A manual connection target requires an asyncio task")
        intent = (self._authenticated_epoch(), self._advance_connection_intent())
        self._manual_connection_tasks[task] = intent[1]
        deadline = self._connection_retirement_deadline()
        try:
            async with self._suspended_reconnection(deadline=deadline):
                await self._retire_manual_connection_tasks(
                    before_generation=intent[1],
                    deadline=deadline,
                )
                yield intent
        finally:
            self._manual_connection_tasks.pop(task, None)

    @asynccontextmanager
    async def _superseding_connection_targets(
        self, *, deadline: float | None = None,
    ) -> AsyncIterator[_ConnectionSupersession]:
        """Invalidate and join all older manual and automatic connection work."""
        generation = self._advance_connection_intent()
        if deadline is None:
            deadline = self._connection_retirement_deadline()
        async with self._suspended_reconnection(deadline=deadline) as reconnector:
            await self._retire_manual_connection_tasks(
                before_generation=generation,
                deadline=deadline,
            )
            yield _ConnectionSupersession(reconnector, deadline)

    def _connection_retirement_deadline(self) -> float:
        return asyncio.get_running_loop().time() + self._connection_retirement_seconds

    async def _retire_manual_connection_tasks(
        self,
        *,
        before_generation: int,
        deadline: float,
    ) -> None:
        current_task = asyncio.current_task()
        pending = {
            task
            for task, generation in self._manual_connection_tasks.items()
            if task is not current_task
            and not task.done()
            and generation < before_generation
        }
        if not pending:
            return
        for task in pending:
            task.cancel()

        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        waiter = asyncio.create_task(asyncio.wait(pending, timeout=remaining))
        caller_cancelled = False
        try:
            await await_owned(waiter)
        except asyncio.CancelledError:
            caller_cancelled = True
        done, still_pending = waiter.result()
        for task in done:
            try:
                task.result()
            except (Exception, asyncio.CancelledError):
                pass
        if still_pending:
            self._terminate_failed_connection_retirement(
                "manual connection target",
                len(still_pending),
            )
        if caller_cancelled:
            raise asyncio.CancelledError

    def retire_unconfirmed_operation(self) -> NoReturn:
        """Retire the provider process after foreground ownership expires."""
        self._terminate_failed_connection_retirement("foreground operation", 1)

    def _terminate_failed_connection_retirement(
        self, failure_kind: str, owner_count: int
    ) -> NoReturn:
        logger.critical(
            "Forced backend exit: connection retirement failed "
            "(%s; %d owner(s))",
            failure_kind,
            owner_count,
        )
        self._terminal_exit(INCOMPLETE_CONNECTION_RETIREMENT_EXIT_CODE)
        raise SystemExit(INCOMPLETE_CONNECTION_RETIREMENT_EXIT_CODE)

    async def _disconnect_until_stable(
        self,
        *,
        deadline: float | None = None,
        transitional_only: bool = False,
    ) -> None:
        """Own Core Down until no queued replacement can start later."""
        retirement_deadline = (
            deadline
            if deadline is not None
            else self._connection_retirement_deadline()
        )
        await await_owned(
            self._disconnect_until_stable_owned(
                deadline=retirement_deadline,
                transitional_only=transitional_only,
            )
        )

    async def _disconnect_until_stable_owned(
        self,
        *,
        deadline: float,
        transitional_only: bool,
    ) -> None:
        if self._connector is None:
            return
        state_name = type(self._connector.current_state).__name__
        if transitional_only and state_name not in {
            "Connecting", "Disconnecting", "Disconnected"
        }:
            return

        while True:
            observed_revision = self._connector_state_revision
            remaining = max(
                0.0,
                deadline - asyncio.get_running_loop().time(),
            )
            if not remaining:
                self._terminate_failed_connection_retirement("stable disconnect deadline", 1)
            disconnect_task = asyncio.create_task(self._disconnect_barrier())
            _, pending = await asyncio.wait(
                {disconnect_task},
                timeout=remaining,
            )
            if pending:
                self._terminate_failed_connection_retirement(
                    "stable disconnect",
                    len(pending),
                )
            try:
                disconnected_at_barrier = disconnect_task.result()
            except (Exception, asyncio.CancelledError) as error:
                self._terminate_failed_connection_retirement(
                    "stable disconnect raised " + type(error).__name__,
                    1,
                )

            if disconnected_at_barrier:
                return
            await self._wait_for_connector_state_change(
                observed_revision,
                deadline,
            )
            # A state property or notification is not a completed Core event
            # barrier. Reenter through public Down after every observed change.

    async def _disconnect_barrier(self) -> bool:
        await self._connector.disconnect()
        # Sample in the task that crossed Core's public event barrier. Sampling
        # later in its waiter could observe a different, unfinished event.
        return type(self._connector.current_state).__name__ == "Disconnected"

    async def _wait_for_connector_state_change(
        self,
        observed_revision: int,
        deadline: float,
    ) -> None:
        while self._connector_state_revision == observed_revision:
            self._connector_state_changed.clear()
            if self._connector_state_revision != observed_revision:
                return
            remaining = max(
                0.0,
                deadline - asyncio.get_running_loop().time(),
            )
            try:
                await asyncio.wait_for(
                    self._connector_state_changed.wait(),
                    timeout=remaining,
                )
            except TimeoutError:
                self._terminate_failed_connection_retirement(
                    "stable disconnect state transition",
                    1,
                )

    def _manual_connection_is_current(
        self, authentication_epoch: int, connection_intent: int
    ) -> bool:
        self._require_authenticated_epoch(authentication_epoch)
        return connection_intent == self._connection_intent_generation

    def _settings_from_core(self, settings: Any) -> VpnSettings:
        disconnected = (
            type(self._connector.current_state).__name__.lower() == "disconnected"
        )
        translated = translate_vpn_settings(
            settings,
            protocols=self._available_protocols(settings.protocol),
            user_tier=self._user_tier(),
            disconnected=disconnected,
            packet_capture_supported=self._protocol_supports_packet_capture(
                settings.protocol
            ),
        )
        if not self._crash_report_submission_enabled:
            return replace(translated, anonymous_crash_reports=False)
        return translated

    def _split_tunneling_from_core(self, settings: Any) -> SplitTunnelingSettings:
        return translate_split_tunneling(
            settings,
            available=bool(self._connector.is_split_tunneling_available),
            user_tier=self._user_tier(),
        )

    def _custom_dns_from_core(self, settings: Any) -> CustomDnsSettings:
        return translate_custom_dns(settings, user_tier=self._user_tier())

    def _available_protocols(self, current_protocol: str) -> tuple[ProtocolInfo, ...]:
        return discover_protocols(self._api, self._connector, current_protocol)

    def _user_tier(self) -> int:
        if not self._logged_in:
            return 0
        return int(self._api.account_data.max_tier)

    @staticmethod
    def _protocol_supports_split_tunneling(protocol: str) -> bool:
        return core_protocol_supports_split_tunneling(protocol)

    def _protocol_supports_packet_capture(self, protocol: str) -> bool:
        return core_protocol_supports_packet_capture(
            self._api, self._connector, protocol
        )

    def _iter_available_protocols(self):
        yield from iter_core_protocols(self._api, self._connector)

    @staticmethod
    def _connection_supports_packet_capture(connection: Any) -> bool:
        return PacketCaptureCoordinator.connection_supports_capture(connection)

    @staticmethod
    def _mode_value(mode: Any) -> str:
        return core_mode_value(mode)

    async def disconnect(self, *, deadline: float | None = None) -> None:
        # A connecting tunnel may be cancelled outside the controller's main
        # operation lock. Serialize that preemption boundary here so multiple
        # authorized clients cannot overlap suspend/resume scopes and release
        # automatic reconnection while another disconnect is still active.
        if deadline is None:
            deadline = self._connection_retirement_deadline()
        self._require_cleanup_dispatch_time(deadline)
        try:
            async with self._superseding_connection_targets(deadline=deadline) as supersession:
                async with self._serialized_connection_lifecycle(deadline=deadline):
                    await self._disconnect_until_stable(deadline=supersession.deadline)
        except ScopeAdmissionExpired:
            self._terminate_failed_connection_retirement("disconnect ownership", 1)

    async def login(self, username: str, password: str) -> None:
        async with self._serialized_authentication_transition():
            await self._login(username, password)

    async def _login(self, username: str, password: str) -> None:
        if self._account_restart_required or self._session_services_started:
            raise UserVisibleRuntimeError(
                "Sign out and restart the backend before replacing the Proton account"
            )
        if self._logged_in:
            raise UserVisibleRuntimeError("The Proton account is already signed in")
        # Invalidate account-scoped work accepted for any earlier session,
        # including a signed-out session whose credentials are being replaced.
        self._authentication_epoch += 1
        settings = await self._load_settings()
        self._kill_switch = self._kill_switch_value(settings)
        if self._kill_switch == 2:
            self._auth_state = "signed_out"
            self._status_message = (
                "Disable the permanent kill switch before signing in"
            )
            self._publish_snapshot()
            raise UserVisibleRuntimeError(
                "Disable the permanent kill switch before signing in"
            )
        self._auth_state = "signing_in"
        self._status_message = "Signing in…"
        self._publish_snapshot()
        try:
            result = await self._api.login(username, password)
        except Exception as error:
            await self._reconcile_authentication_failure(error)
            return

        if not result.authenticated:
            self._auth_state = "signed_out"
            self._status_message = "Incorrect username or password"
            self._publish_snapshot()
            return
        if result.twofa_required:
            self._auth_state = "two_factor"
            self._status_message = "Enter your two-factor authentication code"
            self._publish_snapshot()
            return
        await self._complete_login()

    async def submit_two_factor(self, code: str) -> None:
        async with self._serialized_authentication_transition():
            await self._submit_two_factor(code)

    async def _submit_two_factor(self, code: str) -> None:
        if self._auth_state not in {"two_factor", "fido_error"}:
            raise UserVisibleRuntimeError("No two-factor authentication is pending")
        self._status_message = "Verifying the two-factor code…"
        self._publish_snapshot()
        try:
            result = await self._api.submit_2fa_code(code)
        except Exception as error:
            await self._reconcile_authentication_failure(
                error, fallback_state="two_factor"
            )
            return
        if not result.success:
            self._auth_state = "two_factor"
            self._status_message = "Incorrect two-factor authentication code"
            self._publish_snapshot()
            return
        await self._complete_login()

    async def cancel_login(self) -> None:
        async with self._serialized_authentication_transition():
            await self._cancel_login()

    async def _cancel_login(self) -> None:
        if self._session_services_started or self._account_restart_required:
            await self._logout()
            return
        self._authentication_epoch += 1
        await self.cancel_fido2()
        try:
            await self._api.logout()
        except Exception:
            core_logged_in = await self._core_logged_in_after_failure()
            if core_logged_in is False:
                await self._set_signed_out("Sign-in cancelled")
                return
            if core_logged_in is True:
                self._logged_in = True
                try:
                    await self._enable_session_services()
                except Exception:
                    self._auth_state = "signed_in_degraded"
                    self._status_message = (
                        "Sign-in could not be cancelled; the Proton session is "
                        "still active but its services could not be restored"
                    )
                else:
                    self._auth_state = "signed_in"
                    self._status_message = (
                        "Sign-in could not be cancelled; the Proton session is "
                        "still active"
                    )
                self._publish_snapshot()
                raise UserVisibleRuntimeError(self._status_message) from None
            self._logged_in = False
            self._auth_state = "authentication_unknown"
            self._status_message = (
                "Proton could not confirm whether sign-in was cancelled; "
                "restart the backend before trying again"
            )
            self._publish_snapshot()
            raise UserVisibleRuntimeError(self._status_message) from None
        await self._set_signed_out("Sign-in cancelled")

    async def begin_fido2(self) -> None:
        async with self._serialized_authentication_transition():
            await self._begin_fido2()

    async def _begin_fido2(self) -> None:
        if self._auth_state not in {"two_factor", "fido_error"}:
            raise UserVisibleRuntimeError("No two-factor authentication is pending")
        if not _cancellable_fido2_available(self._api):
            raise UserVisibleRuntimeError(
                "Security-key authentication is unavailable because the "
                "installed Proton Core cannot safely cancel key selection"
            )

        loop = asyncio.get_running_loop()
        interaction = FidoInteraction(loop, self._set_auth_status)
        self._fido_interaction = interaction
        self._set_auth_status(
            "fido_waiting",
            "Insert your security key and follow its prompts",
        )
        try:
            await await_owned(
                self._create_owned_child_task(
                    self._authenticate_fido2(interaction), authentication=True,
                ),
                cancel_operation=interaction.cancel,
            )
        finally:
            if self._fido_interaction is interaction:
                self._fido_interaction = None

    async def _authenticate_fido2(self, interaction: FidoInteraction) -> None:
        """Own assertion submission and reconciliation after prompt cancellation."""
        # The caller may cancel after creating this task but before it starts.
        if interaction.cancelled:
            self._set_auth_status(
                "two_factor", "Security-key authentication cancelled"
            )
            return
        assertion_operation = self._api.generate_2fa_fido2_assertion(
            interaction,
            interaction.cancel_assertion,
        )
        try:
            assertion = await await_owned(assertion_operation)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if interaction.cancelled:
                self._set_auth_status(
                    "two_factor", "Security-key authentication cancelled"
                )
            else:
                await self._reconcile_authentication_failure(
                    error,
                    fallback_state="fido_error",
                    fido_error=True,
                )
            return
        if interaction.cancelled:
            self._set_auth_status(
                "two_factor", "Security-key authentication cancelled"
            )
            return
        try:
            result = await self._api.submit_2fa_fido2(assertion)
        except Exception as error:
            # Once Core accepts an assertion it may persist authentication
            # before a later session-data fetch fails. A concurrent UI
            # cancel cannot classify that late failure as signed out.
            await self._reconcile_authentication_failure(
                error,
                fallback_state="fido_error",
                fido_error=True,
            )
            return

        if not result.success:
            self._set_auth_status(
                "fido_error", "The security key was not accepted"
            )
            return
        await self._complete_login()

    async def submit_fido2_pin(self, pin: str) -> None:
        if not self._fido_interaction or not self._fido_interaction.provide_pin(pin):
            raise UserVisibleRuntimeError("No security key is waiting for a PIN")
        self._set_auth_status("fido_waiting", "Waiting for the security key…")

    async def cancel_fido2(self) -> None:
        if self._fido_interaction:
            self._fido_interaction.cancel()

    async def logout(self) -> None:
        async with self._serialized_authentication_transition():
            await self._logout()

    async def _logout(self) -> None:
        # Logout, ordinary Disconnect, reconnection-policy changes, and
        # teardown all mutate the same connector/reconnector pair.  One
        # lifecycle barrier prevents any of those sibling operations from
        # overtaking another.
        # Persist before changing credentials; a crash or a late old refresh
        # cannot turn a replacement login into same-process session reuse.
        self._account_restart_required = True
        try:
            self._account_transition.store(tunnel_retired=False)
            async with self._superseding_connection_targets() as supersession:
                async with self._serialized_connection_lifecycle():
                    await self._logout_with_disconnect_barrier(
                        supersession.deadline
                    )
        except (Exception, asyncio.CancelledError):
            # A store can replace its record before directory fsync fails.
            # Keep the fence and possible handoff; expose recovery even when
            # failure precedes the later logout compensation/publication path.
            self._publish_snapshot()
            raise

    async def _logout_with_disconnect_barrier(self, deadline: float) -> None:
        # Advance before the first await: reads already in flight belong to the
        # outgoing account even while the public snapshot still says signed in.
        self._authentication_epoch += 1
        await self.cancel_fido2()
        settings = await self._load_settings()
        previous_kill_switch = self._kill_switch_value(settings)
        kill_switch_changed = previous_kill_switch != 0
        kill_switch_zero_task: asyncio.Task[None] | None = None
        try:
            if self._reconnector:
                await self._reconnector.disable()
            await self._disable_refresher()
            await self._disconnect_until_stable(deadline=deadline)
            self._account_transition.store(tunnel_retired=True)
            if kill_switch_changed:
                # Proton Core persists settings in an executor. Shield this
                # task so outer cancellation cannot abandon a worker that may
                # later overwrite the compensating protection write.
                settings.killswitch = 0
                kill_switch_zero_task = self._create_owned_child_task(
                    self._save_settings(settings),
                    authentication=True,
                    connection=True,
                )
                await asyncio.shield(kill_switch_zero_task)
            self._kill_switch = 0
            await await_owned(self._api.logout())
        except (Exception, asyncio.CancelledError) as error:
            recovery, recovery_cancelled = await self._finish_logout_recovery(
                settings,
                previous_kill_switch,
                kill_switch_zero_task,
            )
            if isinstance(error, asyncio.CancelledError):
                raise
            if recovery_cancelled:
                raise asyncio.CancelledError() from None
            if recovery.core_logged_in is False:
                raise UserVisibleRuntimeError(
                    "Signed out, but Proton could not complete some local cleanup"
                ) from None
            if not recovery.protection_restored:
                raise UserVisibleRuntimeError(
                    "Sign-out failed and the kill switch setting could not be "
                    "confirmed; restart the backend and review VPN settings "
                    "before reconnecting"
                ) from None
            if recovery.session_recovery_failed:
                raise UserVisibleRuntimeError(
                    "Sign-out failed and the Proton session could not be restored"
                ) from None
            error_name = type(error).__name__
            if error_name in {"ProtonAPINotReachable", "ProtonAPINotAvailable"}:
                raise UserVisibleRuntimeError(
                    "Proton's API is unreachable; sign-out was not completed"
                ) from None
            raise UserVisibleRuntimeError(
                "Proton could not complete sign-out"
            ) from None
        self._publish_signed_out_state("Signed out", "signed_out")

    async def disable_kill_switch_for_login(self) -> None:
        async with self._serialized_authentication_transition():
            await self._disable_kill_switch_for_login()

    async def _disable_kill_switch_for_login(self) -> None:
        authentication_epoch = self._authentication_epoch
        settings = await self._load_settings(authentication_epoch)
        # Always ask Core to apply the disabled state. Its save operation can
        # persist the value before connector application fails, so a retry may
        # load zero even while the live connector still has protection active.
        settings.killswitch = 0
        await self._save_settings(settings, authentication_epoch)
        self._kill_switch = 0
        self._status_message = "Kill switch disabled; you can now sign in"
        self._publish_snapshot()

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        if enabled:
            async with self._suspended_reconnection() as reconnector:
                async with self._serialized_connection_lifecycle():
                    await self._apply_reconnection_enabled(enabled, reconnector)
            return

        async with self._superseding_connection_targets() as supersession:
            async with self._serialized_connection_lifecycle():
                await self._disconnect_until_stable(
                    deadline=supersession.deadline,
                    transitional_only=True,
                )
                await self._apply_reconnection_enabled(
                    enabled,
                    supersession.reconnector,
                )

    async def _apply_reconnection_enabled(
        self,
        enabled: bool,
        reconnector: AsyncReconnector | None,
    ) -> None:
        self._reconnection_enabled = enabled
        if not reconnector:
            return
        if enabled and self._logged_in and self._session_services_enabled:
            reconnector.enable()
        else:
            await reconnector.disable()

    async def close(self, *, deadline: float | None = None) -> None:
        """Retain one teardown and terminal result under the first deadline."""
        if self._close_task is None:
            if deadline is None:
                deadline = self._connection_retirement_deadline()
            # Fence callback admission before taking a lock its worker may need.
            # This owns our callback work, not Core's refresh children.
            self._refresher_errors.stop()
            if self._reconnector:
                self._reconnector.begin_shutdown()
            self._close_task = asyncio.create_task(self._close_before_deadline(deadline))
        await await_owned(self._close_task)

    async def _close_before_deadline(self, deadline: float) -> None:
        self._require_close_time(deadline)
        self._close_work_task = asyncio.create_task(self._close_once(deadline))
        self._close_work_task.add_done_callback(self._observe_close_work)
        _, pending = await asyncio.wait(
            {self._close_work_task},
            timeout=max(0.0, deadline - asyncio.get_running_loop().time()),
        )
        if pending:
            # Do not cancel mandatory provider cleanup or pretend it joined.
            # Keep the worker, forbid later stages, and let the service's
            # existing failed-shutdown/process boundary retire remaining work.
            raise TimeoutError("Proton Core teardown outlived the shutdown deadline")
        self._close_work_task.result()

    @staticmethod
    def _observe_close_work(task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            task.exception()

    @staticmethod
    def _require_close_time(deadline: float) -> None:
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("Proton Core teardown outlived the shutdown deadline")

    async def _close_once(self, deadline: float) -> None:
        await self._retire_refresher_error_handler(deadline)
        async with self._serialized_authentication_transition():
            self._require_close_time(deadline)
            await self._close(deadline)

    async def _retire_refresher_error_handler(self, deadline: float) -> None:
        worker = self._refresher_errors.task
        if worker is not None:
            _, pending = await asyncio.wait(
                {worker}, timeout=max(0.0, deadline - asyncio.get_running_loop().time())
            )
            if pending:
                raise TimeoutError("Background session recovery exceeded the shutdown deadline")

    async def _close(self, deadline: float) -> None:
        # Disconnect may deliberately bypass the controller operation lock to
        # preempt a connecting tunnel. Drain that accepted scope before
        # unregistering Core observers or disabling the reconnector.
        async with self._superseding_connection_targets(deadline=deadline) as supersession:
            async with self._serialized_connection_lifecycle():
                self._require_close_time(deadline)
                await self._disconnect_until_stable(
                    deadline=supersession.deadline,
                    transitional_only=True,
                )
                self._require_close_time(deadline)
                await self.cancel_fido2()
                if self._packet_capture_active:
                    self._require_close_time(deadline)
                    try:
                        await self._packet_capture.stop(deadline=deadline)
                    except RuntimeError:
                        # Preserve active state when Core cannot confirm the stop.
                        # The service must not report a false clean shutdown state.
                        pass
                self._require_close_time(deadline)
                self._packet_capture.release_for_shutdown()
                if supersession.reconnector:
                    await supersession.reconnector.disable(deadline=deadline)
                self._require_close_time(deadline)
                if self._api:
                    self._api.refresher.set_error_callback(ignore_retired_refresh_error)
                    self._api.refresher.set_server_list_updated_callback(None)
                    self._api.refresher.set_server_loads_updated_callback(None)
                    location_callback_setter = getattr(
                        self._api.refresher,
                        "set_location_names_updated_callback",
                        None,
                    )
                    if callable(location_callback_setter):
                        location_callback_setter(None)
                if self._connector:
                    self._connector.unregister(self)
                if (
                    self._api
                    and self._session_services_state
                    is not _SessionServicesState.DISABLED
                ):
                    self._require_close_time(deadline)
                    await self._disable_refresher()

    def status_update(self, state: Any) -> None:
        self._connector_state_revision += 1
        self._connector_state_changed.set()
        if self._initialized and self._callback:
            self._callback(self._snapshot_from_state(state))

    def _on_reconnector_status(self, message: str) -> None:
        self._status_message = message
        if self._initialized and self._callback and self._connector:
            self._callback(self._snapshot_from_state(self._connector.current_state))

    def _on_server_list_updated(self) -> None:
        self._invalidate_search_projection()
        if self._server_data_callback:
            self._server_data_callback(True)

    def _on_server_loads_updated(self) -> None:
        if self._server_data_callback:
            self._server_data_callback(False)

    def _on_location_names_updated(self) -> None:
        self._invalidate_search_projection()
        if self._server_data_callback:
            self._server_data_callback(True)

    def _invalidate_search_projection(self) -> None:
        self._server_list_generation += 1
        self._search_projection = None

    def _current_refresher_failure(self, failure: RefreshFailure) -> bool:
        return (
            self._refresher_errors.is_current(failure)
            and failure.epoch == self._authentication_epoch
            and self._logged_in
            and not self._account_restart_required
        )

    async def _handle_refresher_failure(self, failure: RefreshFailure) -> None:
        async with self._serialized_authentication_transition():
            if not self._current_refresher_failure(failure):
                return
            if failure.kind is RefreshFailureKind.AUTHENTICATION:
                await self._expire_session(failure.epoch)
            else:
                # An escaped exception removes that job from Core scheduling.
                # Preserve the account, tunnel, other jobs and recovery policy;
                # report degraded updates rather than inventing a retry.
                self._background_refresh_degraded = True
                self._publish_snapshot()

    def _refresher_handler_failed(self, failure: RefreshFailure) -> None:
        if not self._current_refresher_failure(failure):
            return
        self._publish_signed_out_state(
            "Background session recovery failed; restart the backend before continuing",
            "authentication_unknown",
        )

    async def _complete_login(self) -> None:
        try:
            await self._enable_session_services()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Enable can create refresh children before failing. Only a new
            # process may clear this session and admit another account.
            self._account_transition.store(tunnel_retired=False)
            self._account_restart_required = True
            try:
                async with self._serialized_connection_lifecycle():
                    await self._disconnect_until_stable()
                    self._account_transition.store(tunnel_retired=True)
                    await await_owned(self._api.logout())
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

            core_logged_in = await self._core_logged_in_after_failure()
            if core_logged_in is False:
                await self._set_signed_out(
                    "Proton session services could not start; sign-in was rolled back"
                )
            elif core_logged_in is True:
                self._logged_in = True
                self._auth_state = "signed_in_degraded"
                self._status_message = (
                    "Signed in, but Proton session services could not start and "
                    "the session could not be cleared"
                )
                self._publish_snapshot()
            else:
                await self._quiesce_session_services()
                self._logged_in = False
                self._auth_state = "authentication_unknown"
                self._status_message = (
                    "Proton session services could not start and the account "
                    "state could not be confirmed; restart the backend before "
                    "continuing"
                )
                self._search_projection = None
                self._publish_snapshot()

            if core_logged_in is True:
                raise UserVisibleRuntimeError(
                    "Sign-in completed, but session services failed and the "
                    "authenticated session could not be cleared"
                ) from None
            if core_logged_in is None:
                raise UserVisibleRuntimeError(
                    "Sign-in could not be completed and Proton could not confirm "
                    "the account state; restart the backend before continuing"
                ) from None
            raise UserVisibleRuntimeError(
                "Proton session services could not start; sign-in was rolled back"
            ) from None
        self._logged_in = True
        self._auth_state = "signed_in"
        self._status_message = ""
        self._publish_snapshot()

    async def _enable_session_services(self) -> None:
        async with self._serialized_connection_lifecycle():
            await self._enable_session_services_with_connection_barrier()

    async def _enable_session_services_with_connection_barrier(self) -> None:
        if self._account_restart_required:
            raise UserVisibleRuntimeError(
                "Restart the backend to finish the account transition"
            )
        try:
            if (
                self._session_services_state
                is _SessionServicesState.CLEANUP_REQUIRED
            ):
                # An earlier enable/disable may have committed before its
                # acknowledgement failed. Obtain a stopped-scheduler
                # acknowledgement before starting it again; not a child join.
                await self._disable_refresher()
            if self._session_services_state is _SessionServicesState.DISABLED:
                self._session_services_state = (
                    _SessionServicesState.CLEANUP_REQUIRED
                )
                self._session_services_started = True
                self._api.refresher.set_error_callback(
                    self._refresher_errors.bind(self._authentication_epoch)
                )
                await await_owned(self._api.refresher.enable())
                self._session_services_state = _SessionServicesState.ENABLED
                self._background_refresh_degraded = False
            if not self._reconnector:
                self._reconnector = AsyncReconnector(
                    self._connector,
                    self._api.refresher,
                    self._on_reconnector_status,
                    authentication_epoch_source=lambda: self._authentication_epoch,
                    authentication_epoch_validator=(
                        lambda epoch: epoch == self._authentication_epoch
                        and self._logged_in
                    ),
                    authentication_error_callback=self._raise_session_error,
                    connection_attempt=self._attempt_reconnection,
                )
            if self._reconnection_enabled:
                self._reconnector.enable()
        except (Exception, asyncio.CancelledError):
            if self._reconnector and self._reconnector.enabled:
                async with self._suspended_reconnection() as reconnector:
                    if reconnector and reconnector.enabled:
                        await reconnector.disable()
            if (
                self._session_services_state
                is not _SessionServicesState.DISABLED
            ):
                try:
                    await self._disable_refresher()
                except (Exception, asyncio.CancelledError):
                    # Preserve the original enable/reconnector failure. The
                    # tri-state retains cleanup authority for recovery/close.
                    pass
            raise

    async def _disable_refresher(self) -> None:
        """Acknowledge disabled scheduling, not retirement of Core's children."""
        if (
            not self._api
            or self._session_services_state is _SessionServicesState.DISABLED
        ):
            return
        self._refresher_errors.invalidate()
        self._session_services_state = _SessionServicesState.CLEANUP_REQUIRED
        await await_owned(self._api.refresher.disable())
        self._session_services_state = _SessionServicesState.DISABLED

    async def _set_signed_out(
        self, message: str, auth_state: str = "signed_out"
    ) -> None:
        try:
            async with self._superseding_connection_targets() as supersession:
                async with self._serialized_connection_lifecycle():
                    await self._disconnect_until_stable(
                        deadline=supersession.deadline,
                        transitional_only=True,
                    )
                    if supersession.reconnector:
                        try:
                            await supersession.reconnector.disable()
                        except Exception:
                            # Authentication state is authoritative. Observer
                            # cleanup cannot preserve stale signed-in state.
                            pass
                    try:
                        await self._disable_refresher()
                    except Exception:
                        # Keep CLEANUP_REQUIRED for a later recovery or close.
                        pass
        except Exception:
            # Retry retirement itself is best effort on this terminal path.
            pass
        self._publish_signed_out_state(message, auth_state)

    def _publish_signed_out_state(self, message: str, auth_state: str) -> None:
        self._logged_in = False
        self._auth_state = auth_state
        self._status_message = message
        self._search_projection = None
        self._publish_snapshot()

    async def _finish_logout_recovery(
        self,
        settings: Any,
        previous_kill_switch: int,
        kill_switch_zero_task: asyncio.Task[None] | None,
    ) -> tuple[_LogoutRecoveryOutcome, bool]:
        """Finish bounded logout repair despite repeated outer cancellation."""

        recovery_task = self._create_owned_child_task(
            self._recover_failed_logout(
                settings,
                previous_kill_switch,
                kill_switch_zero_task,
            ),
            authentication=True,
            connection=True,
        )
        cancellation_requested = False
        while not recovery_task.done():
            try:
                await asyncio.shield(recovery_task)
            except asyncio.CancelledError:
                cancellation_requested = True
        return recovery_task.result(), cancellation_requested

    async def _recover_failed_logout(
        self,
        settings: Any,
        previous_kill_switch: int,
        kill_switch_zero_task: asyncio.Task[None] | None,
    ) -> _LogoutRecoveryOutcome:
        """Publish only protection and session state confirmed after logout failure."""

        if kill_switch_zero_task is not None:
            completed, _ = await asyncio.wait(
                (kill_switch_zero_task,), timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS
            )
            try:
                await await_owned(kill_switch_zero_task)
            except (Exception, asyncio.CancelledError):
                # A failed acknowledgement is still terminal. The provider may
                # have committed, so a compensating write remains required.
                pass
            if not completed:
                # Preserve the conservative stage-expiry result, but only
                # release ownership after the original write has retired.
                return await self._publish_unknown_protection(None)

        try:
            async with asyncio.timeout(LOGOUT_RECOVERY_TIMEOUT_SECONDS):
                core_logged_in = await self._core_logged_in_after_failure()
        except TimeoutError:
            core_logged_in = None
        if core_logged_in is False:
            await self._quiesce_session_services()
            self._publish_signed_out_state("Signed out", "signed_out")
            return _LogoutRecoveryOutcome(False, True, False)

        protection_restored = True
        if kill_switch_zero_task is not None:
            settings.killswitch = previous_kill_switch
            try:
                async with asyncio.timeout(LOGOUT_RECOVERY_TIMEOUT_SECONDS):
                    await await_owned(self._create_owned_child_task(
                        self._save_settings(settings),
                        authentication=True,
                        connection=True,
                    ))
            except (Exception, asyncio.CancelledError):
                protection_restored = False

        if not protection_restored:
            return await self._publish_unknown_protection(core_logged_in)

        self._kill_switch = previous_kill_switch

        if core_logged_in is True:
            self._logged_in = True
            if self._account_restart_required:
                # Keep compensation for the old protection setting, but never
                # restart refreshers after accepting an account transition.
                self._auth_state = "account_restart_required"
                self._status_message = (
                    "Sign-out is incomplete; restart the backend to finish it"
                )
                self._publish_snapshot()
                return _LogoutRecoveryOutcome(True, True, False)
            session_recovery_failed = False
            try:
                async with asyncio.timeout(LOGOUT_RECOVERY_TIMEOUT_SECONDS):
                    await await_owned(self._create_owned_child_task(
                        self._enable_session_services(),
                        authentication=True,
                        connection=True,
                    ))
            except (Exception, asyncio.CancelledError):
                session_recovery_failed = True
            self._auth_state = (
                "signed_in_degraded" if session_recovery_failed else "signed_in"
            )
            if session_recovery_failed:
                self._status_message = (
                    "Sign-out was interrupted and Proton session services could "
                    "not be restored"
                )
            else:
                self._status_message = (
                    "Sign-out was interrupted; the Proton session remains active"
                )
            self._publish_snapshot()
            return _LogoutRecoveryOutcome(True, True, session_recovery_failed)

        await self._quiesce_session_services()
        self._logged_in = False
        self._auth_state = "authentication_unknown"
        self._status_message = (
            "Sign-out was interrupted and Proton could not confirm the account "
            "state; restart the backend before continuing"
        )
        self._search_projection = None
        self._publish_snapshot()
        return _LogoutRecoveryOutcome(None, True, False)

    async def _publish_unknown_protection(
        self, core_logged_in: bool | None
    ) -> _LogoutRecoveryOutcome:
        await self._quiesce_session_services()
        # Zero is the conservative projection: persistence is ambiguous, so
        # never claim that permanent protection remains enabled.
        self._kill_switch = 0
        self._logged_in = False
        self._auth_state = "protection_unknown"
        self._status_message = (
            "Proton could not confirm the kill switch setting after an "
            "interrupted sign-out; restart the backend and review VPN "
            "settings before reconnecting"
        )
        self._search_projection = None
        self._publish_snapshot()
        return _LogoutRecoveryOutcome(core_logged_in, False, True)

    async def _quiesce_session_services(self) -> bool:
        """Best-effort bounded stop used before publishing recovery-required state."""

        try:
            async with asyncio.timeout(LOGOUT_RECOVERY_TIMEOUT_SECONDS):
                async with self._suspended_reconnection():
                    async with self._serialized_connection_lifecycle():
                        return await (
                            self._quiesce_session_services_with_connection_barrier()
                        )
        except (Exception, asyncio.CancelledError):
            return True

    async def _quiesce_session_services_with_connection_barrier(self) -> bool:

        cleanup_failed = False
        if self._reconnector:
            try:
                async with asyncio.timeout(LOGOUT_RECOVERY_TIMEOUT_SECONDS):
                    await self._reconnector.disable()
            except (Exception, asyncio.CancelledError):
                cleanup_failed = True
        if self._api:
            try:
                async with asyncio.timeout(LOGOUT_RECOVERY_TIMEOUT_SECONDS):
                    await self._disable_refresher()
            except (Exception, asyncio.CancelledError):
                cleanup_failed = True
        return cleanup_failed

    async def _core_logged_in_after_failure(self) -> bool | None:
        """Read Core's persisted authentication state after a partial operation.

        Proton Core login and logout are multi-stage operations. An exception
        does not establish whether the SSO session was persisted or revoked, so
        rollback decisions must query Core instead of trusting adapter flags.
        A failed query is deliberately treated as unknown by callers.
        """

        try:
            return bool(await run_in_daemon_thread(self._api.is_user_logged_in))
        except asyncio.CancelledError:
            raise
        except Exception:
            return None

    async def _reconcile_authentication_failure(
        self,
        error: Exception,
        *,
        fallback_state: str = "signed_out",
        fido_error: bool = False,
    ) -> None:
        """Publish authentication state derived from Core, never an assumption."""

        core_logged_in = await self._core_logged_in_after_failure()
        if core_logged_in is False:
            if fido_error:
                self._handle_fido2_error(error)
            else:
                self._handle_authentication_error(error, fallback_state)
            return
        if core_logged_in is True:
            self._logged_in = True
            try:
                await self._enable_session_services()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._auth_state = "signed_in_degraded"
                self._status_message = (
                    "Authentication completed, but Proton session services "
                    "could not start"
                )
                self._publish_snapshot()
                raise UserVisibleRuntimeError(self._status_message) from None
            self._auth_state = "signed_in"
            self._status_message = (
                "Signed in; Proton reported an incomplete authentication response"
            )
            self._publish_snapshot()
            return

        self._logged_in = False
        self._auth_state = "authentication_unknown"
        self._status_message = (
            "Proton could not confirm whether authentication completed; "
            "restart the backend before trying again"
        )
        self._publish_snapshot()
        raise UserVisibleRuntimeError(self._status_message) from None

    async def _raise_session_error(
        self, error: Exception, authentication_epoch: int
    ) -> None:
        if not is_proton_authentication_needed(error):
            raise error
        async with self._serialized_authentication_transition():
            await self._expire_session(authentication_epoch)
        raise SessionExpiredError(
            "Your Proton session expired; sign in again"
        ) from None

    def _authenticated_epoch(self) -> int:
        authentication_epoch = self._authentication_epoch
        self._require_authenticated_epoch(authentication_epoch)
        return authentication_epoch

    def _require_authentication_epoch(self, authentication_epoch: int) -> None:
        if authentication_epoch != self._authentication_epoch:
            raise SessionExpiredError("The Proton account session changed") from None

    def _require_authenticated_epoch(self, authentication_epoch: int) -> None:
        self._require_authentication_epoch(authentication_epoch)
        if not self._logged_in or self._account_restart_required:
            raise SessionExpiredError("The Proton account session changed") from None

    def _serialized_authentication_transition(self) -> AbstractAsyncContextManager[None]:
        return self._authentication_scope.enter()

    def _create_owned_child_task(
        self,
        coroutine: Coroutine[Any, Any, _OwnedTaskResult],
        *,
        authentication: bool = False,
        connection: bool = False,
    ) -> asyncio.Task[_OwnedTaskResult]:
        scopes = []
        if authentication:
            scopes.append(self._authentication_scope)
        if connection:
            scopes.append(self._connection_scope)
        return create_owned_task(coroutine, *scopes)

    @asynccontextmanager
    async def _suspended_reconnection(
        self, *, deadline: float | None = None
    ) -> AsyncIterator[AsyncReconnector | None]:
        """Temporarily quiesce retry work with exact ownership pairing."""
        reconnector = self._reconnector
        if reconnector is None:
            yield None
            return
        retirement_deadline = (
            deadline
            if deadline is not None
            else self._connection_retirement_deadline()
        )
        try:
            async with reconnector.suspended(deadline=retirement_deadline):
                yield reconnector
        except ReconnectionRetirementTimeout:
            self._terminate_failed_connection_retirement(
                "automatic reconnect",
                len(reconnector._retiring_retry_tasks),
            )

    def _serialized_connection_lifecycle(
        self, *, deadline: float | None = None
    ) -> AbstractAsyncContextManager[None]:
        return self._connection_scope.enter(deadline=deadline)

    async def _expire_session(self, authentication_epoch: int) -> None:
        if authentication_epoch != self._authentication_epoch:
            # The failure belongs to an obsolete account/session. It remains a
            # failed request, but it has no authority to sign out or disable
            # services for the replacement session.
            raise SessionExpiredError(
                "The Proton account session changed"
            ) from None
        # Invalidate sibling requests from the expired session before cleanup
        # yields to the event loop.
        self._authentication_epoch += 1
        self._advance_connection_intent()
        session_services_need_cleanup = (
            self._session_services_state is not _SessionServicesState.DISABLED
        )
        self._publish_signed_out_state(
            "Your Proton session expired; sign in again",
            "expired",
        )
        cleanup_failed = False
        try:
            deadline = self._connection_retirement_deadline()
            async with self._suspended_reconnection(deadline=deadline) as reconnector:
                await self._retire_manual_connection_tasks(
                    before_generation=self._connection_intent_generation,
                    deadline=deadline,
                )
                async with self._serialized_connection_lifecycle():
                    await self._disconnect_until_stable(
                        deadline=deadline,
                        transitional_only=True,
                    )
                    if reconnector:
                        try:
                            await reconnector.disable()
                        except Exception:
                            cleanup_failed = True
                    if session_services_need_cleanup:
                        try:
                            await self._disable_refresher()
                        except Exception:
                            cleanup_failed = True
        except Exception:
            cleanup_failed = True
        message = "Your Proton session expired; sign in again"
        if cleanup_failed:
            message = (
                "Your Proton session expired; sign in again. Some local session "
                "cleanup could not complete"
            )
        if cleanup_failed:
            self._publish_signed_out_state(message, "expired")

    def _set_auth_status(self, state: str, message: str) -> None:
        self._auth_state = state
        self._status_message = message
        self._publish_snapshot()

    def _publish_snapshot(self) -> None:
        if self._initialized and self._callback and self._connector:
            self._callback(self._snapshot_from_state(self._connector.current_state))

    def _handle_authentication_error(
        self,
        error: Exception,
        fallback_state: str = "signed_out",
    ) -> None:
        error_name = type(error).__name__
        if error_name == "ProtonAPIHumanVerificationNeeded":
            self._auth_state = "human_verification"
            self._status_message = (
                "Proton requires additional human verification. "
                "Complete it in your Proton account, then try again."
            )
        elif error_name in {"ProtonAPINotReachable", "ProtonAPINotAvailable"}:
            self._auth_state = fallback_state
            self._status_message = "Proton's API is currently unreachable"
        elif isinstance(error, ValueError):
            self._auth_state = fallback_state
            self._status_message = "Enter a valid Proton username"
        else:
            self._auth_state = fallback_state
            self._status_message = "Proton could not complete authentication"
        self._publish_snapshot()

    def _handle_fido2_error(self, error: Exception) -> None:
        messages = {
            "SecurityKeyNotFoundError": "No security key was detected",
            "InvalidSecurityKeyError": "That security key is not linked to this account",
            "SecurityKeyPINNotSetError": "The security key does not have a PIN configured",
            "SecurityKeyPINInvalidError": "The security-key PIN was incorrect",
            "SecurityKeyTimeoutError": "The security-key request timed out",
            "Fido2NotSupportedError": "Security-key authentication is unavailable",
        }
        self._set_auth_status(
            "fido_error",
            messages.get(type(error).__name__, "Security-key authentication failed"),
        )

    def _snapshot_from_state(self, state: Any) -> VpnSnapshot:
        if core_state_name(state) in {"disconnected", "device_disconnected"}:
            if self._packet_capture_active or self._packet_capture_watchdog_task:
                self._finish_packet_capture_state()
        degraded = (
            self._background_refresh_degraded
            and self._logged_in
            and not self._account_restart_required
            and self._auth_state == "signed_in"
        )
        return translate_snapshot(
            state,
            SnapshotContext(
                connector=self._connector,
                api=self._api,
                startup_compatible=self._startup_compatible,
                logged_in=self._logged_in and not self._account_restart_required,
                auth_state=(
                    "account_restart_required"
                    if self._account_restart_required
                    and self._auth_state not in {
                        "authentication_unknown", "settings_unavailable", "protection_unknown"
                    }
                    else "signed_in_degraded" if degraded else self._auth_state
                ),
                reconnection_enabled=self._reconnection_enabled,
                kill_switch=self._kill_switch,
                packet_capture_active=self._packet_capture_active,
                core_memory_optimized=self._core_memory_optimized,
                core_version=self._core_version,
                status_message=(
                    self._status_message
                    or (BACKGROUND_REFRESH_DEGRADED_MESSAGE if degraded else "")
                ),
            ),
        )

    @staticmethod
    def _kill_switch_value(settings: Any) -> int:
        return core_kill_switch_value(settings)
