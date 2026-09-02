# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Proton core and safe demo backend adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .async_utils import run_in_daemon_thread
from .demo_adapter import DemoCoreAdapter
from .errors import (
    SessionExpiredError,
    UserVisibleRuntimeError,
    UserVisibleValueError,
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
from .features import CRASH_REPORT_SUBMISSION_ENABLED
from .packet_capture import (
    PACKET_CAPTURE_MAX_SECONDS,
    PACKET_CAPTURE_STOP_ATTEMPT_SECONDS,
    PacketCaptureCoordinator,
)
from .reconnector import AsyncReconnector
from .search_projection import ServerSearchProjection


__all__ = [
    "DemoCoreAdapter",
    "ProtonCoreAdapter",
    "_core_memory_optimization_behavior",
]


LOGOUT_RECOVERY_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class _LogoutRecoveryOutcome:
    core_logged_in: bool | None
    protection_restored: bool
    session_recovery_failed: bool


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
    ):
        self._api: Any = api
        self._connector: Any = None
        self._callback: SnapshotCallback | None = None
        self._server_data_callback: ServerDataCallback | None = None
        self._logged_in = False
        self._reconnector: AsyncReconnector | None = None
        self._reconnection_enabled = True
        self._status_message = ""
        self._auth_state = "signed_out"
        self._session_services_enabled = False
        self._fido_interaction: FidoInteraction | None = None
        self._crash_report_submission_enabled = crash_report_submission_enabled
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
        """Keep initialization alive while durable capture recovery is pending."""
        return self._packet_capture.has_pending_recovery()

    async def initialize(
        self,
        callback: SnapshotCallback,
        server_data_callback: ServerDataCallback | None = None,
    ) -> VpnSnapshot:
        self._callback = callback
        self._server_data_callback = server_data_callback
        self._core_memory_optimized = _core_memory_optimizations_active()
        self._core_version = _core_package_version()
        if self._api is None:
            from proton.vpn.core.api import ProtonVPNAPI
            from proton.vpn.core.session_holder import ClientTypeMetadata

            self._api = ProtonVPNAPI(ClientTypeMetadata(type="gui"))

        self._connector = await self._api.get_vpn_connector()
        self._connector.register(self)
        # Packet capture is external to this process. Reacquire any durable
        # completion-unknown generation before any potentially interactive
        # Secret Service access or backend-readiness publication.
        await self._packet_capture.recover(self._connector)
        # Proton SSO reaches Secret Service through a synchronous keyring API.
        # Warm the cached session away from the D-Bus asyncio thread so a
        # provider unlock prompt (KeePassXC, KWallet, etc.) cannot freeze the
        # entire backend while waiting for user approval. Durable capture
        # recovery is already supervised if that approval remains pending.
        self._logged_in = await run_in_daemon_thread(self._api.is_user_logged_in)
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

        if self._logged_in:
            await self._enable_session_services()

        return self._snapshot_from_state(self._connector.current_state)

    async def connect_fastest(self) -> None:
        server_list = await self._get_server_list()
        logical_server = server_list.get_fastest()
        await self._connect_logical(logical_server)

    async def connect_fastest_with_feature(self, feature: str) -> None:
        await self.connect_fastest_with_features((feature,))

    async def connect_fastest_with_features(self, features: tuple[str, ...]) -> None:
        server_list = await self._get_server_list()
        logical_server = self._fastest_matching(
            server_list, server_list.logicals, features
        )
        await self._connect_logical(logical_server)

    @staticmethod
    def _fastest_matching(server_list, servers, features: tuple[str, ...]):
        return core_fastest_matching(server_list, servers, features)

    async def get_countries(self) -> list[CountryInfo]:
        server_list = await self._get_server_list()
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
        return countries

    async def get_server_groups(self, country_code: str) -> list[ServerGroupInfo]:
        from proton.vpn.session.servers import ServerFeatureEnum

        server_list = await self._get_server_list()
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
        return result

    async def get_group_servers(
        self, country_code: str, group_kind: str, group_name: str
    ) -> list[ServerInfo]:
        server_list = await self._get_server_list()
        group = self._server_group(server_list, country_code, group_kind, group_name)
        servers = [self._server_info(server_list, server) for server in group.servers]
        return sorted(
            servers,
            key=lambda item: (
                not item.accessible,
                item.under_maintenance,
                item.load,
                item.name,
            ),
        )

    async def get_server_loads(self, country_code: str) -> list[ServerLoadInfo]:
        server_list = await self._get_server_list()
        return [
            ServerLoadInfo(server.name, server.load or 0)
            for server in server_list.logicals
            if server.exit_country.upper() == country_code
        ]

    async def search_locations(self, query: str) -> list[LocationSearchInfo]:
        from proton.vpn.session.servers import ServerFeatureEnum
        from proton.vpn.session.servers.logicals import (
            sort_servers_alphabetically_by_country_and_server_name,
        )

        server_list = await self._get_server_list()
        if (
            self._search_projection is None
            or self._search_projection.generation != self._server_list_generation
        ):
            self._search_projection = ServerSearchProjection.build(
                server_list,
                self._server_list_generation,
                ServerFeatureEnum.SECURE_CORE,
                sort_servers_alphabetically_by_country_and_server_name,
            )
        return self._search_projection.search(server_list, query)

    async def get_settings(self) -> VpnSettings:
        settings = await self._load_settings()
        return self._settings_from_core(settings)

    async def get_split_tunneling(self) -> SplitTunnelingSettings:
        settings = await self._load_settings()
        return self._split_tunneling_from_core(settings)

    async def get_custom_dns(self) -> CustomDnsSettings:
        settings = await self._load_settings()
        return self._custom_dns_from_core(settings)

    async def update_settings(self, patch: dict[str, SettingsValue]) -> VpnSettings:
        if (
            patch.get("anonymousCrashReports") is True
            and not self._crash_report_submission_enabled
        ):
            raise UserVisibleRuntimeError(
                "Anonymous crash reporting is disabled in this unofficial community build"
            )
        settings = await self._load_settings()
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
            ) = previous_values

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

        await self._save_settings_transactionally(
            settings,
            rollback,
            protection_sensitive="killSwitch" in patch,
        )
        return self._settings_from_core(settings)

    async def update_split_tunneling(
        self, patch: dict[str, SplitTunnelingValue]
    ) -> SplitTunnelingSettings:
        settings = await self._load_settings()
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

        await self._save_settings_transactionally(settings, rollback)
        return self._split_tunneling_from_core(settings)

    async def update_custom_dns(
        self, patch: dict[str, CustomDnsValue]
    ) -> CustomDnsSettings:
        settings = await self._load_settings()
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

        await self._save_settings_transactionally(settings, rollback)
        return self._custom_dns_from_core(settings)

    async def _load_settings(self):
        try:
            settings = await self._api.load_settings()
        except Exception as error:
            if type(error).__name__ == "ProtonAPIAuthenticationNeeded":
                await self._raise_session_error(error)
            raise UserVisibleRuntimeError(
                "Proton could not load the VPN settings"
            ) from None
        if self._crash_report_submission_enabled:
            return settings

        try:
            if bool(settings.anonymous_crash_reports):
                settings.anonymous_crash_reports = False
                await self._save_settings(settings)
        finally:
            # Core's public load_settings method mirrors the persisted value
            # into UsageReporting before it returns. Keep the in-memory sender
            # disabled even if persistence or connector application fails.
            usage_reporting = getattr(self._api, "usage_reporting", None)
            if usage_reporting is not None:
                usage_reporting.enabled = False
        return settings

    async def _save_settings(self, settings: Any) -> None:
        try:
            await self._api.save_settings(settings)
        except Exception as error:
            if type(error).__name__ == "ProtonAPIAuthenticationNeeded":
                await self._raise_session_error(error)
            raise UserVisibleRuntimeError(
                "Proton could not save the VPN settings"
            ) from None

    async def _save_settings_transactionally(
        self,
        settings: Any,
        rollback: Callable[[], None],
        *,
        protection_sensitive: bool = False,
    ) -> None:
        """Compensate a user setting write whose commit status is ambiguous."""

        save_task = asyncio.create_task(self._save_settings(settings))
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

        recovery_task = asyncio.create_task(
            self._recover_failed_settings_save(
                settings,
                rollback,
                save_task,
                protection_sensitive=protection_sensitive,
            )
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
    ) -> bool:
        completed, _ = await asyncio.wait(
            (save_task,), timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS
        )
        if not completed:
            # The executor-backed Core write may still commit. Do not race a
            # compensation against it; require a backend restart instead.
            save_task.add_done_callback(self._consume_background_task_result)
            await self._publish_unknown_settings(protection_sensitive)
            return False
        try:
            save_task.result()
        except SessionExpiredError:
            rollback()
            raise
        except (Exception, asyncio.CancelledError):
            # A failed acknowledgement can follow a completed persistence
            # write, so compensation is still mandatory.
            pass

        rollback()
        try:
            await asyncio.wait_for(
                self._save_settings(settings),
                timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS,
            )
        except SessionExpiredError:
            raise
        except (Exception, asyncio.CancelledError):
            await self._publish_unknown_settings(protection_sensitive)
            return False
        return True

    async def _publish_unknown_settings(self, protection_sensitive: bool) -> None:
        await self._quiesce_session_services()
        self._logged_in = False
        self._session_services_enabled = False
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
        server_list = await self._get_server_list()
        await self._connect_logical(server_list.get_fastest_in_country(country_code))

    async def connect_country_with_features(
        self, country_code: str, features: tuple[str, ...]
    ) -> None:
        server_list = await self._get_server_list()
        country = self._country(server_list, country_code)
        logical_server = self._fastest_matching(server_list, country.servers, features)
        await self._connect_logical(logical_server)

    async def connect_group(
        self, country_code: str, group_kind: str, group_name: str
    ) -> None:
        server_list = await self._get_server_list()
        group = self._server_group(server_list, country_code, group_kind, group_name)
        available = server_list.get_available_servers(
            group.servers, server_list.user_tier
        )
        logical_server = server_list.get_fastest_server(available)
        if logical_server is None:
            raise UserVisibleRuntimeError("No server available in the current tier")
        await self._connect_logical(logical_server)

    async def connect_group_with_features(
        self,
        country_code: str,
        group_kind: str,
        group_name: str,
        features: tuple[str, ...],
    ) -> None:
        server_list = await self._get_server_list()
        group = self._server_group(server_list, country_code, group_kind, group_name)
        logical_server = self._fastest_matching(server_list, group.servers, features)
        await self._connect_logical(logical_server)

    async def connect_server(self, server_name: str) -> None:
        server_list = await self._get_server_list()
        await self._connect_logical(server_list.get_by_name(server_name))

    async def start_packet_capture(self, directory_path: str) -> None:
        await self._packet_capture.start(self._connector, directory_path)

    async def stop_packet_capture(self) -> None:
        await self._packet_capture.stop()

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
        await submit_core_support_report(self._api, report)

    async def take_pending_nps_survey(self) -> bool:
        return await take_core_nps_survey(self._api)

    async def submit_nps_survey(self, response: NpsSurveyResponse) -> None:
        await submit_core_nps_survey(self._api, response)

    async def _get_server_list(self):
        try:
            return await self._api.refresher.get_up_to_date_server_list()
        except Exception as error:
            await self._raise_session_error(error)

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

    async def _connect_logical(self, logical_server) -> None:
        try:
            client_config = await self._api.refresher.get_up_to_date_client_config()
            vpn_server = self._connector.get_vpn_server(logical_server, client_config)
            settings = await self._load_settings()
            await self._connector.connect(vpn_server, protocol=settings.protocol)
        except Exception as error:
            await self._raise_session_error(error)

    def _settings_from_core(self, settings: Any) -> VpnSettings:
        self._kill_switch = self._kill_switch_value(settings)
        disconnected = (
            type(self._connector.current_state).__name__.lower() == "disconnected"
        )
        return translate_vpn_settings(
            settings,
            protocols=self._available_protocols(settings.protocol),
            user_tier=self._user_tier(),
            disconnected=disconnected,
            packet_capture_supported=self._protocol_supports_packet_capture(
                settings.protocol
            ),
        )

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

    async def disconnect(self) -> None:
        await self._connector.disconnect()

    async def login(self, username: str, password: str) -> None:
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
        if self._auth_state not in {"two_factor", "fido_error"}:
            raise UserVisibleRuntimeError("No two-factor authentication is pending")
        if not bool(self._api.supports_fido2):
            raise UserVisibleRuntimeError("Security-key authentication is unavailable")

        loop = asyncio.get_running_loop()
        interaction = FidoInteraction(loop, self._set_auth_status)
        self._fido_interaction = interaction
        self._set_auth_status(
            "fido_waiting",
            "Insert your security key and follow its prompts",
        )
        try:
            try:
                assertion = await self._api.generate_2fa_fido2_assertion(
                    interaction,
                    interaction.cancel_assertion,
                )
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
        finally:
            self._fido_interaction = None

    async def submit_fido2_pin(self, pin: str) -> None:
        if not self._fido_interaction or not self._fido_interaction.provide_pin(pin):
            raise UserVisibleRuntimeError("No security key is waiting for a PIN")
        self._set_auth_status("fido_waiting", "Waiting for the security key…")

    async def cancel_fido2(self) -> None:
        if self._fido_interaction:
            self._fido_interaction.cancel()

    async def logout(self) -> None:
        await self.cancel_fido2()
        if type(self._connector.current_state).__name__ != "Disconnected":
            await self._connector.disconnect()
        settings = await self._load_settings()
        previous_kill_switch = self._kill_switch_value(settings)
        kill_switch_changed = previous_kill_switch != 0
        kill_switch_zero_task: asyncio.Task[None] | None = None
        try:
            if kill_switch_changed:
                # Proton Core persists settings in an executor. Shield this
                # task so outer cancellation cannot abandon a worker that may
                # later overwrite the compensating protection write.
                settings.killswitch = 0
                kill_switch_zero_task = asyncio.create_task(
                    self._save_settings(settings)
                )
                await asyncio.shield(kill_switch_zero_task)
            self._kill_switch = 0
            if self._reconnector:
                await self._reconnector.disable()
            self._session_services_enabled = False
            await self._api.logout()
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
        await self._set_signed_out("Signed out")

    async def disable_kill_switch_for_login(self) -> None:
        settings = await self._load_settings()
        # Always ask Core to apply the disabled state. Its save operation can
        # persist the value before connector application fails, so a retry may
        # load zero even while the live connector still has protection active.
        settings.killswitch = 0
        await self._save_settings(settings)
        self._kill_switch = 0
        self._status_message = "Kill switch disabled; you can now sign in"
        self._publish_snapshot()

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        self._reconnection_enabled = enabled
        if not self._reconnector:
            return
        if enabled and self._logged_in and self._session_services_enabled:
            self._reconnector.enable()
        else:
            await self._reconnector.disable()

    async def close(self) -> None:
        await self.cancel_fido2()
        if self._packet_capture_active:
            try:
                await self.stop_packet_capture()
            except RuntimeError:
                # Preserve active state when Core cannot confirm the stop. The
                # service must not report a false clean shutdown condition.
                pass
        self._packet_capture.release_for_shutdown()
        if self._api:
            self._api.refresher.set_server_list_updated_callback(None)
            self._api.refresher.set_server_loads_updated_callback(None)
            location_callback_setter = getattr(
                self._api.refresher, "set_location_names_updated_callback", None
            )
            if callable(location_callback_setter):
                location_callback_setter(None)
        if self._reconnector:
            await self._reconnector.disable()
        if self._connector:
            self._connector.unregister(self)
        if self._api and self._session_services_enabled:
            await self._api.refresher.disable()

    def status_update(self, state: Any) -> None:
        if self._callback:
            self._callback(self._snapshot_from_state(state))

    def _on_reconnector_status(self, message: str) -> None:
        self._status_message = message
        if self._callback and self._connector:
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

    async def _complete_login(self) -> None:
        try:
            await self._enable_session_services()
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await self._api.logout()
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
        refresher_enabled_here = False
        try:
            if not self._session_services_enabled:
                await self._api.refresher.enable()
                self._session_services_enabled = True
                refresher_enabled_here = True
            if not self._reconnector:
                self._reconnector = AsyncReconnector(
                    self._connector,
                    self._api.refresher,
                    self._on_reconnector_status,
                )
            if self._reconnection_enabled:
                self._reconnector.enable()
        except (Exception, asyncio.CancelledError):
            if self._reconnector and self._reconnector.enabled:
                await self._reconnector.disable()
            if refresher_enabled_here:
                try:
                    await self._api.refresher.disable()
                finally:
                    self._session_services_enabled = False
            raise

    async def _set_signed_out(
        self, message: str, auth_state: str = "signed_out"
    ) -> None:
        if self._reconnector:
            try:
                await self._reconnector.disable()
            except Exception:
                # Authentication state is authoritative. Observer cleanup is
                # best effort and must never preserve a stale signed-in state.
                pass
        self._publish_signed_out_state(message, auth_state)

    def _publish_signed_out_state(self, message: str, auth_state: str) -> None:
        self._logged_in = False
        self._auth_state = auth_state
        self._status_message = message
        self._session_services_enabled = False
        self._search_projection = None
        self._publish_snapshot()

    async def _finish_logout_recovery(
        self,
        settings: Any,
        previous_kill_switch: int,
        kill_switch_zero_task: asyncio.Task[None] | None,
    ) -> tuple[_LogoutRecoveryOutcome, bool]:
        """Finish bounded logout repair despite repeated outer cancellation."""

        recovery_task = asyncio.create_task(
            self._recover_failed_logout(
                settings,
                previous_kill_switch,
                kill_switch_zero_task,
            )
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
            try:
                await asyncio.wait_for(
                    asyncio.shield(kill_switch_zero_task),
                    timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                # Never race compensation against Core's still-live executor
                # worker. Its eventual zero write agrees with the conservative
                # recovery projection published below.
                kill_switch_zero_task.add_done_callback(
                    self._consume_background_task_result
                )
                return await self._publish_unknown_protection(None)
            except (Exception, asyncio.CancelledError):
                # A failed acknowledgement is still terminal. The provider may
                # have committed, so a compensating write remains required.
                pass

        try:
            core_logged_in = await asyncio.wait_for(
                self._core_logged_in_after_failure(),
                timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS,
            )
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
                await asyncio.wait_for(
                    self._save_settings(settings),
                    timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS,
                )
            except (Exception, asyncio.CancelledError):
                protection_restored = False

        if not protection_restored:
            return await self._publish_unknown_protection(core_logged_in)

        self._kill_switch = previous_kill_switch

        if core_logged_in is True:
            self._logged_in = True
            session_recovery_failed = False
            try:
                await asyncio.wait_for(
                    self._enable_session_services(),
                    timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS,
                )
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
        self._session_services_enabled = False
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

    @staticmethod
    def _consume_background_task_result(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except (Exception, asyncio.CancelledError):
            pass

    async def _quiesce_session_services(self) -> bool:
        """Best-effort bounded stop used before publishing recovery-required state."""

        cleanup_failed = False
        if self._reconnector:
            try:
                await asyncio.wait_for(
                    self._reconnector.disable(),
                    timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS,
                )
            except (Exception, asyncio.CancelledError):
                cleanup_failed = True
        if self._api:
            try:
                await asyncio.wait_for(
                    self._api.refresher.disable(),
                    timeout=LOGOUT_RECOVERY_TIMEOUT_SECONDS,
                )
            except (Exception, asyncio.CancelledError):
                cleanup_failed = True
        self._session_services_enabled = False
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

    async def _raise_session_error(self, error: Exception):
        if type(error).__name__ != "ProtonAPIAuthenticationNeeded":
            raise error
        session_services_were_enabled = self._session_services_enabled
        self._publish_signed_out_state(
            "Your Proton session expired; sign in again",
            "expired",
        )
        cleanup_failed = False
        if self._reconnector:
            try:
                await self._reconnector.disable()
            except Exception:
                cleanup_failed = True
        if session_services_were_enabled:
            try:
                await self._api.refresher.disable()
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
        raise SessionExpiredError(
            "Your Proton session expired; sign in again"
        ) from None

    def _set_auth_status(self, state: str, message: str) -> None:
        self._auth_state = state
        self._status_message = message
        self._publish_snapshot()

    def _publish_snapshot(self) -> None:
        if self._callback and self._connector:
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
        return translate_snapshot(
            state,
            SnapshotContext(
                connector=self._connector,
                api=self._api,
                startup_compatible=self._startup_compatible,
                logged_in=self._logged_in,
                auth_state=self._auth_state,
                reconnection_enabled=self._reconnection_enabled,
                kill_switch=self._kill_switch,
                packet_capture_active=self._packet_capture_active,
                core_memory_optimized=self._core_memory_optimized,
                core_version=self._core_version,
                status_message=self._status_message,
            ),
        )

    @staticmethod
    def _kill_switch_value(settings: Any) -> int:
        return core_kill_switch_value(settings)
