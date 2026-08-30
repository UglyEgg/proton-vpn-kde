"""Proton core and safe demo backend adapters."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from . import __version__
from .async_utils import run_in_daemon_thread
from .errors import UserVisibleRuntimeError, UserVisibleValueError
from .controller import (
    CountryInfo,
    CustomDnsServer,
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
    normalize_server_features,
)
from .fido_interaction import FidoInteraction
from .features import CRASH_REPORT_SUBMISSION_ENABLED
from .reconnector import AsyncReconnector
from .search_projection import ServerSearchProjection, fold_search_text
from .support import collect_support_logs


def _supports_split_tunneling(protocol: str) -> bool:
    return protocol == "wireguard" or protocol.startswith("protun-")


def _core_memory_optimization_behavior(logicals_module: Any) -> bool:
    """Checks both string-sharing paths without touching live Core state."""
    deduplicate = getattr(logicals_module, "_deduplicate_server_strings", None)
    hook_factory = getattr(logicals_module, "_server_string_object_hook", None)
    if not callable(deduplicate) or not callable(hook_factory):
        return False

    first = bytes("phase8-runtime-probe.example", "utf-8").decode("utf-8")
    second = bytes("phase8-runtime-probe.example", "utf-8").decode("utf-8")
    if first is second:
        return False
    decoded: list[dict[str, Any]] = [
        {"Domain": first, "Servers": [{"Domain": second}]}
    ]
    try:
        deduplicate(decoded)
    except Exception:
        return False
    if decoded[0]["Domain"] is not decoded[0]["Servers"][0]["Domain"]:
        return False

    third = bytes("phase8-cache-probe.example", "utf-8").decode("utf-8")
    fourth = bytes("phase8-cache-probe.example", "utf-8").decode("utf-8")
    if third is fourth:
        return False
    try:
        object_hook = hook_factory()
        first_item = object_hook({"Domain": third})
        second_item = object_hook({"Domain": fourth})
    except Exception:
        return False
    return first_item["Domain"] is second_item["Domain"]


def _core_memory_optimizations_active() -> bool:
    try:
        from proton.vpn.session.servers import logicals
    except (ImportError, ModuleNotFoundError):
        return False
    return _core_memory_optimization_behavior(logicals)


def _core_package_version() -> str:
    try:
        return version("proton-vpn-api-core")
    except PackageNotFoundError:
        return ""


class DemoCoreAdapter:
    """Deterministic adapter that never touches the network or credentials."""

    def __init__(
        self,
        logged_in: bool = True,
        kill_switch: int = 0,
        nps_survey_available: bool = False,
    ):
        self._callback: SnapshotCallback | None = None
        self._server_data_callback: ServerDataCallback | None = None
        self._logged_in = logged_in
        self._auth_state = "signed_in" if logged_in else "signed_out"
        self._reconnection_enabled = True
        self._connection_cancelled = False
        self._settings = VpnSettings(
            protocols=(
                ProtocolInfo("wireguard", "WireGuard"),
                ProtocolInfo("protun-udp", "WireGuard UDP"),
                ProtocolInfo("openvpn-udp", "OpenVPN (UDP)"),
                ProtocolInfo("openvpn-tcp", "OpenVPN (TCP)"),
            ),
            paid_features_available=logged_in,
            kill_switch=kill_switch,
            anonymous_crash_reports=False,
        )
        self._split_tunneling = SplitTunnelingSettings(
            available=True,
            paid_features_available=logged_in,
        )
        self._custom_dns = CustomDnsSettings(
            paid_features_available=logged_in,
        )
        self._packet_capture_active = False
        self._nps_survey_available = nps_survey_available
        self.last_support_report: SupportReport | None = None
        self.last_nps_response: NpsSurveyResponse | None = None
        self._snapshot = self._build_snapshot(message="Safe demo backend")

    async def initialize(
        self,
        callback: SnapshotCallback,
        server_data_callback: ServerDataCallback | None = None,
    ) -> VpnSnapshot:
        self._callback = callback
        self._server_data_callback = server_data_callback
        return self._snapshot

    async def connect_fastest(self) -> None:
        self._connection_cancelled = False
        await self._transition("connecting", "")
        await asyncio.sleep(0.15)
        if not self._connection_cancelled:
            await self._transition("connected", "US-IL#600")

    async def connect_fastest_with_feature(self, feature: str) -> None:
        await self.connect_fastest_with_features((feature,))

    async def connect_fastest_with_features(self, features: tuple[str, ...]) -> None:
        servers = [
            *self._servers_for_country("CH"),
            *self._servers_for_country("US"),
            *await self.get_group_servers("CH", "secure-core", "Via Secure Core"),
        ]
        await self._connect_fastest_matching(servers, features)

    async def _connect_fastest_matching(
        self, servers: list[ServerInfo], features: tuple[str, ...]
    ) -> None:
        normalized = normalize_server_features(features)
        feature_attributes = {
            "p2p": "p2p",
            "streaming": "streaming",
            "tor": "tor",
            "secure-core": "secure_core",
        }
        available = [
            server
            for server in servers
            if server.accessible
            and not server.under_maintenance
            and all(
                bool(getattr(server, feature_attributes[feature]))
                for feature in normalized
            )
        ]
        if not available:
            raise UserVisibleRuntimeError("No server available in the current tier")
        await self.connect_server(min(available, key=lambda server: server.load).name)

    async def get_countries(self) -> list[CountryInfo]:
        return [
            CountryInfo("CH", 4, free=True),
            CountryInfo("US", 5, free=True),
        ]

    async def get_server_groups(self, country_code: str) -> list[ServerGroupInfo]:
        demo_groups = {
            "CH": [
                ServerGroupInfo(
                    "location",
                    "Zurich",
                    3,
                    tor=True,
                    p2p=True,
                    streaming=True,
                ),
                ServerGroupInfo(
                    "secure-core",
                    "Via Secure Core",
                    1,
                    secure_core=True,
                    p2p=True,
                ),
            ],
            "US": [
                ServerGroupInfo("location", "Chicago, IL", 1, p2p=True),
                ServerGroupInfo("location", "New York, NY", 1, streaming=True),
            ],
        }
        return demo_groups.get(country_code, [])

    async def get_group_servers(
        self, country_code: str, group_kind: str, group_name: str
    ) -> list[ServerInfo]:
        if country_code == "CH" and group_kind == "secure-core":
            return [
                ServerInfo(
                    "CH-DE#1",
                    "Via Germany",
                    entry_country="DE",
                    load=35,
                    secure_core=True,
                    p2p=True,
                )
            ]
        return [
            server
            for server in self._servers_for_country(country_code)
            if server.location == group_name
        ]

    @staticmethod
    def _servers_for_country(country_code: str) -> list[ServerInfo]:
        demo_servers = {
            "CH": [
                ServerInfo("CH#101", "Zurich", 24, p2p=True, streaming=True),
                ServerInfo("CH#202", "Zurich", 51, streaming=True),
                ServerInfo("CH#TOR1", "Zurich", 42, tor=True),
            ],
            "US": [
                ServerInfo("US-IL#600", "Chicago, IL", 32, p2p=True),
                ServerInfo("US-NY#88", "New York, NY", 47, streaming=True),
            ],
        }
        return demo_servers.get(country_code, [])

    async def get_server_loads(self, country_code: str) -> list[ServerLoadInfo]:
        servers = list(self._servers_for_country(country_code))
        if country_code == "CH":
            servers.extend(
                await self.get_group_servers("CH", "secure-core", "Via Secure Core")
            )
        return [ServerLoadInfo(server.name, server.load) for server in servers]

    async def search_locations(self, query: str) -> list[LocationSearchInfo]:
        needle = fold_search_text(query)
        locations: dict[tuple[str, str], LocationSearchInfo] = {}
        servers: list[LocationSearchInfo] = []
        for country_code in ("CH", "US"):
            country_servers = list(self._servers_for_country(country_code))
            if country_code == "CH":
                country_servers.extend(
                    await self.get_group_servers("CH", "secure-core", "Via Secure Core")
                )
            for server in country_servers:
                if server.location and needle in fold_search_text(server.location):
                    locations[(country_code, server.location)] = LocationSearchInfo(
                        kind="location",
                        name=server.location,
                        country_code=country_code,
                        group_name=server.location,
                        accessible=server.accessible,
                    )
                if server.accessible and needle in fold_search_text(server.name):
                    servers.append(
                        LocationSearchInfo(
                            kind="server",
                            name=server.name,
                            country_code=country_code,
                            location=server.location,
                            group_kind=(
                                "secure-core" if server.secure_core else "location"
                            ),
                            group_name=(
                                "Via Secure Core"
                                if server.secure_core
                                else server.location
                            ),
                            load=server.load,
                        )
                    )
        return [
            *sorted(
                locations.values(),
                key=lambda item: (item.name, item.country_code),
            )[:100],
            *sorted(servers, key=lambda item: item.name)[:100],
        ]

    async def get_settings(self) -> VpnSettings:
        return replace(
            self._settings,
            paid_features_available=self._logged_in,
            protocol_editable=self._snapshot.state == "disconnected",
            kill_switch_editable=self._snapshot.state == "disconnected",
            packet_capture_supported=self._settings.protocol.startswith("protun-"),
        )

    async def update_settings(self, patch: dict[str, SettingsValue]) -> VpnSettings:
        if self._snapshot.state != "disconnected" and (
            {"protocol", "killSwitch"} & set(patch)
        ):
            raise UserVisibleRuntimeError(
                "Disconnect the VPN before changing protocol or kill switch"
            )
        if not self._logged_in and (
            {"netShield", "vpnAccelerator", "moderateNat", "portForwarding"}
            & set(patch)
        ):
            raise UserVisibleRuntimeError(
                "This setting requires a paid Proton VPN plan"
            )
        replacements = {
            {
                "protocol": "protocol",
                "killSwitch": "kill_switch",
                "netShield": "net_shield",
                "vpnAccelerator": "vpn_accelerator",
                "moderateNat": "moderate_nat",
                "portForwarding": "port_forwarding",
                "ipv6": "ipv6",
                "anonymousCrashReports": "anonymous_crash_reports",
            }[key]: value
            for key, value in patch.items()
        }
        protocol = replacements.get("protocol")
        if protocol is not None and protocol not in {
            item.id for item in self._settings.protocols
        }:
            raise UserVisibleValueError("Select an available VPN protocol")
        # settings_patch_from_json owns the field/type allowlist. The dynamic
        # field mapping cannot be represented by dataclasses.replace's static
        # per-field overload.
        self._settings = replace(self._settings, **replacements)  # type: ignore[arg-type]
        return await self.get_settings()

    async def get_split_tunneling(self) -> SplitTunnelingSettings:
        return replace(
            self._split_tunneling,
            paid_features_available=self._logged_in,
        )

    async def update_split_tunneling(
        self, patch: dict[str, SplitTunnelingValue]
    ) -> SplitTunnelingSettings:
        if not self._logged_in:
            raise UserVisibleRuntimeError("A Proton account session is required")
        if not self._split_tunneling.available:
            raise UserVisibleRuntimeError(
                "Split tunneling is unavailable on this system"
            )
        if patch.get("enabled") is True:
            if self._settings.kill_switch != 0:
                raise UserVisibleValueError(
                    "Disable the kill switch before enabling split tunneling"
                )
            if not _supports_split_tunneling(self._settings.protocol):
                raise UserVisibleValueError(
                    "Select WireGuard or a compatible protocol first"
                )

        replacements = {
            {
                "enabled": "enabled",
                "mode": "mode",
                "excludeAppPaths": "exclude_app_paths",
                "includeAppPaths": "include_app_paths",
                "excludeIpRanges": "exclude_ip_ranges",
                "includeIpRanges": "include_ip_ranges",
            }[key]: tuple(value) if isinstance(value, list) else value
            for key, value in patch.items()
        }
        # split_tunneling_patch_from_json owns the field/type allowlist.
        updated = replace(
            self._split_tunneling, **replacements  # type: ignore[arg-type]
        )
        if (
            updated.enabled
            and updated.mode == "include"
            and not updated.include_app_paths
            and not updated.include_ip_ranges
        ):
            raise UserVisibleValueError(
                "Select at least one included application or IP range before enabling this mode"
            )
        self._split_tunneling = updated
        self._settings = replace(
            self._settings,
            split_tunneling_enabled=updated.enabled,
        )
        return await self.get_split_tunneling()

    async def get_custom_dns(self) -> CustomDnsSettings:
        return replace(
            self._custom_dns,
            paid_features_available=self._logged_in,
        )

    async def update_custom_dns(
        self, patch: dict[str, CustomDnsValue]
    ) -> CustomDnsSettings:
        if not self._logged_in:
            raise UserVisibleRuntimeError("A Proton account session is required")
        final_enabled = patch.get("enabled", self._custom_dns.enabled)
        if final_enabled and self._settings.net_shield != 0:
            raise UserVisibleValueError("Disable NetShield before enabling custom DNS")
        replacements: dict[str, Any] = {}
        if "enabled" in patch:
            replacements["enabled"] = bool(patch["enabled"])
        if "servers" in patch:
            server_values = patch["servers"]
            if not isinstance(server_values, list):
                raise UserVisibleValueError("The custom-DNS servers are invalid")
            replacements["servers"] = tuple(
                CustomDnsServer(
                    address=str(server["address"]),
                    enabled=bool(server["enabled"]),
                )
                for server in server_values
                if isinstance(server, dict)
            )
        self._custom_dns = replace(self._custom_dns, **replacements)
        self._settings = replace(
            self._settings,
            custom_dns_enabled=self._custom_dns.enabled,
        )
        return await self.get_custom_dns()

    async def connect_country(self, country_code: str) -> None:
        self._connection_cancelled = False
        await self._transition("connecting", "")
        await asyncio.sleep(0.15)
        if not self._connection_cancelled:
            await self._transition("connected", f"{country_code}#FASTEST")

    async def connect_country_with_features(
        self, country_code: str, features: tuple[str, ...]
    ) -> None:
        servers = list(self._servers_for_country(country_code))
        if country_code == "CH":
            servers.extend(
                await self.get_group_servers("CH", "secure-core", "Via Secure Core")
            )
        await self._connect_fastest_matching(servers, features)

    async def connect_group(
        self, country_code: str, group_kind: str, group_name: str
    ) -> None:
        servers = await self.get_group_servers(country_code, group_kind, group_name)
        available = [server for server in servers if server.accessible]
        if not available:
            raise UserVisibleRuntimeError("No server available in the current tier")
        await self.connect_server(min(available, key=lambda server: server.load).name)

    async def connect_group_with_features(
        self,
        country_code: str,
        group_kind: str,
        group_name: str,
        features: tuple[str, ...],
    ) -> None:
        servers = await self.get_group_servers(country_code, group_kind, group_name)
        await self._connect_fastest_matching(servers, features)

    async def connect_server(self, server_name: str) -> None:
        self._connection_cancelled = False
        await self._transition("connecting", server_name)
        await asyncio.sleep(0.15)
        if not self._connection_cancelled:
            await self._transition("connected", server_name)

    async def disconnect(self) -> None:
        self._connection_cancelled = True
        self._packet_capture_active = False
        await self._transition("disconnecting", self._snapshot.server_name)
        await asyncio.sleep(0.1)
        await self._transition("disconnected", "")

    async def start_packet_capture(self, directory_path: str) -> None:
        if self._snapshot.state != "connected":
            raise UserVisibleRuntimeError(
                "Connect the VPN before starting packet capture"
            )
        if not self._settings.protocol.startswith("protun-"):
            raise UserVisibleRuntimeError(
                "The selected protocol does not support packet capture"
            )
        if not Path(directory_path).is_absolute():
            raise UserVisibleValueError("Select a valid packet-capture folder")
        self._packet_capture_active = True
        self._publish(
            self._build_snapshot(
                state=self._snapshot.state,
                server_name=self._snapshot.server_name,
            )
        )

    async def stop_packet_capture(self) -> None:
        self._packet_capture_active = False
        self._publish(
            self._build_snapshot(
                state=self._snapshot.state,
                server_name=self._snapshot.server_name,
            )
        )

    async def submit_support_report(self, report: SupportReport) -> None:
        await asyncio.sleep(0.01)
        self.last_support_report = report

    async def take_pending_nps_survey(self) -> bool:
        available = self._nps_survey_available
        self._nps_survey_available = False
        return available

    async def submit_nps_survey(self, response: NpsSurveyResponse) -> None:
        self.last_nps_response = response

    async def login(self, username: str, password: str) -> None:
        if self._settings.kill_switch == 2:
            raise UserVisibleRuntimeError(
                "Disable the permanent kill switch before signing in"
            )
        await asyncio.sleep(0.05)
        if password == "2fa":
            self._auth_state = "two_factor"
            self._logged_in = False
            self._publish(self._build_snapshot(message="Enter your two-factor code"))
            return
        self._logged_in = True
        self._auth_state = "signed_in"
        self._publish(self._build_snapshot(account_name=username, message=""))

    async def submit_two_factor(self, code: str) -> None:
        await asyncio.sleep(0.05)
        if code not in {"123456", "recovery"}:
            self._publish(self._build_snapshot(message="Incorrect two-factor code"))
            return
        self._logged_in = True
        self._auth_state = "signed_in"
        self._publish(self._build_snapshot(account_name="demo-user", message=""))

    async def cancel_login(self) -> None:
        self._logged_in = False
        self._auth_state = "signed_out"
        self._publish(self._build_snapshot(message="Sign-in cancelled"))

    async def begin_fido2(self) -> None:
        raise UserVisibleRuntimeError(
            "Security-key authentication is unavailable in demo mode"
        )

    async def submit_fido2_pin(self, pin: str) -> None:
        del pin
        raise UserVisibleRuntimeError("No security key is waiting for a PIN")

    async def cancel_fido2(self) -> None:
        return None

    async def logout(self) -> None:
        if self._snapshot.state != "disconnected":
            await self.disconnect()
        self._logged_in = False
        self._auth_state = "signed_out"
        self._settings = replace(self._settings, kill_switch=0)
        self._publish(self._build_snapshot(message="Signed out"))

    async def disable_kill_switch_for_login(self) -> None:
        self._settings = replace(self._settings, kill_switch=0)
        self._publish(
            self._build_snapshot(message="Kill switch disabled; you can now sign in")
        )

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        self._reconnection_enabled = enabled
        self._snapshot = replace(self._snapshot, reconnect_enabled=enabled)
        self._publish(self._snapshot)

    async def close(self) -> None:
        return None

    async def _transition(self, state: str, server_name: str) -> None:
        self._publish(self._build_snapshot(state=state, server_name=server_name))

    def _build_snapshot(
        self,
        *,
        state: str = "disconnected",
        server_name: str = "",
        account_name: str = "demo-user",
        message: str = "",
    ) -> VpnSnapshot:
        details = {
            "CH#101": ("Zurich", "CH", "", False, False, True, True),
            "CH#202": ("Zurich", "CH", "", False, False, False, True),
            "CH#TOR1": ("Zurich", "CH", "", False, True, False, False),
            "CH-DE#1": ("Zurich", "CH", "DE", True, False, True, False),
            "US-IL#600": (
                "Chicago, IL",
                "US",
                "",
                False,
                False,
                True,
                False,
            ),
            "US-NY#88": (
                "New York, NY",
                "US",
                "",
                False,
                False,
                False,
                True,
            ),
            "US#FASTEST": (
                "Fastest available",
                "US",
                "",
                False,
                False,
                False,
                False,
            ),
            "CH#FASTEST": (
                "Fastest available",
                "CH",
                "",
                False,
                False,
                False,
                False,
            ),
        }.get(server_name, ("", "", "", False, False, False, False))
        return VpnSnapshot(
            ready=True,
            logged_in=self._logged_in,
            auth_state=self._auth_state,
            account_name=account_name if self._logged_in else "",
            plan_title="VPN Plus" if self._logged_in else "",
            user_tier=2 if self._logged_in else 0,
            max_connections=10 if self._logged_in else 0,
            reconnect_enabled=self._reconnection_enabled,
            kill_switch=self._settings.kill_switch,
            state=state,
            server_name=server_name,
            server_location=details[0],
            exit_country=details[1],
            entry_country=details[2],
            forwarded_port=(
                51820 if state == "connected" and self._settings.port_forwarding else 0
            ),
            secure_core=details[3],
            tor=details[4],
            p2p=details[5],
            streaming=details[6],
            packet_capture_active=self._packet_capture_active,
            core_memory_optimized=True,
            core_version="demo",
            message=message,
        )

    def _publish(self, snapshot: VpnSnapshot) -> None:
        self._snapshot = snapshot
        if self._callback:
            self._callback(self._snapshot)


PACKET_CAPTURE_MAX_SECONDS = 15 * 60
MAX_ACCEPTED_CORE_CAPTURE_BYTES = 512 * 1024 * 1024


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
        self._packet_capture_active = False
        self._packet_capture_max_seconds = max(0.01, float(packet_capture_max_seconds))
        self._crash_report_submission_enabled = crash_report_submission_enabled
        self._packet_capture_watchdog_task: asyncio.Task | None = None
        self._packet_capture_generation = 0
        self._packet_capture_connection: Any = None
        self._packet_capture_stop_lock = asyncio.Lock()
        self._kill_switch = 0
        self._startup_compatible = True
        self._server_list_generation = 0
        self._search_projection: ServerSearchProjection | None = None
        self._core_memory_optimized = False
        self._core_version = ""

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

        # Proton SSO reaches Secret Service through a synchronous keyring API.
        # Warm the cached session away from the D-Bus asyncio thread so a
        # provider unlock prompt (KeePassXC, KWallet, etc.) cannot freeze the
        # entire backend while waiting for user approval.
        self._logged_in = await run_in_daemon_thread(self._api.is_user_logged_in)
        self._auth_state = "signed_in" if self._logged_in else "signed_out"
        self._connector = await self._api.get_vpn_connector()
        self._connector.register(self)
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
        from proton.vpn.session.servers import ServerFeatureEnum

        normalized = normalize_server_features(features)
        feature_flags = {
            "p2p": ServerFeatureEnum.P2P,
            "streaming": ServerFeatureEnum.STREAMING,
            "tor": ServerFeatureEnum.TOR,
            "secure-core": ServerFeatureEnum.SECURE_CORE,
        }
        requested = ServerFeatureEnum(0)
        for feature in normalized:
            requested |= feature_flags[feature]
        available = server_list.get_available_servers(servers, server_list.user_tier)
        matching = server_list.get_servers_with_features(
            available,
            request_features=requested,
            exclude_features=ServerFeatureEnum(0),
        )
        logical_server = server_list.get_fastest_server(matching)
        if logical_server is None:
            raise UserVisibleRuntimeError("No server available in the current tier")
        return logical_server

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

        await self._save_settings(settings)
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

        await self._save_settings(settings)
        return self._split_tunneling_from_core(settings)

    async def update_custom_dns(
        self, patch: dict[str, CustomDnsValue]
    ) -> CustomDnsSettings:
        settings = await self._load_settings()
        if self._user_tier() < 1:
            raise UserVisibleRuntimeError("Custom DNS requires a paid Proton VPN plan")

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

        await self._save_settings(settings)
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
        if self._packet_capture_active:
            raise UserVisibleRuntimeError("Packet capture is already active")
        if type(self._connector.current_state).__name__.lower() != "connected":
            raise UserVisibleRuntimeError(
                "Connect the VPN before starting packet capture"
            )
        connection = self._connector.current_connection
        if connection is None or not self._connection_supports_packet_capture(
            connection
        ):
            raise UserVisibleRuntimeError(
                "The selected protocol does not support packet capture"
            )
        capture_settings = getattr(connection.settings, "packet_capture", None)
        core_max_bytes = getattr(capture_settings, "max_bytes", None)
        if (
            capture_settings is None
            or isinstance(core_max_bytes, bool)
            or not isinstance(core_max_bytes, int)
            or core_max_bytes <= 0
            or core_max_bytes > MAX_ACCEPTED_CORE_CAPTURE_BYTES
        ):
            raise UserVisibleRuntimeError(
                "The installed Proton Core does not expose a supported packet-capture byte limit"
            )
        path = Path(directory_path)
        if not path.is_absolute():
            raise UserVisibleValueError("Select a valid packet-capture folder")
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise UserVisibleValueError(
                "Select an existing packet-capture folder"
            ) from error
        if not resolved.is_dir() or not os.access(resolved, os.W_OK | os.X_OK):
            raise UserVisibleValueError("Select a writable packet-capture folder")
        try:
            capture_settings.directory_path = str(resolved)
            await connection.start_packet_capture()
        except Exception:
            raise UserVisibleRuntimeError(
                "Proton could not start packet capture"
            ) from None
        self._packet_capture_generation += 1
        generation = self._packet_capture_generation
        self._packet_capture_active = True
        self._packet_capture_connection = connection
        self._cancel_packet_capture_watchdog()
        self._packet_capture_watchdog_task = asyncio.create_task(
            self._packet_capture_watchdog(generation, connection)
        )
        self._publish_snapshot()

    async def stop_packet_capture(self) -> None:
        if not self._packet_capture_active:
            self._cancel_packet_capture_watchdog()
            return
        generation = self._packet_capture_generation
        connection = self._packet_capture_connection
        await self._stop_packet_capture_generation(
            generation,
            connection,
            attempts=1,
            safety_limit=False,
        )

    async def _packet_capture_watchdog(self, generation: int, connection: Any) -> None:
        try:
            await asyncio.sleep(self._packet_capture_max_seconds)
            await self._stop_packet_capture_generation(
                generation,
                connection,
                attempts=3,
                safety_limit=True,
            )
        except asyncio.CancelledError:
            return

    async def _stop_packet_capture_generation(
        self,
        generation: int,
        connection: Any,
        *,
        attempts: int,
        safety_limit: bool,
    ) -> bool:
        """Stop one capture generation exactly once across every caller."""
        async with self._packet_capture_stop_lock:
            if (
                generation != self._packet_capture_generation
                or not self._packet_capture_active
                or connection is not self._packet_capture_connection
            ):
                return False

            for attempt in range(attempts):
                try:
                    if connection is not None:
                        await connection.stop_packet_capture()
                    break
                except Exception:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(1.0)
                        continue
                    if safety_limit:
                        self._status_message = "Packet capture reached its time limit but Proton Core could not stop it"
                        self._publish_snapshot()
                        return False
                    raise UserVisibleRuntimeError(
                        "Proton could not stop packet capture"
                    ) from None

            if (
                generation != self._packet_capture_generation
                or connection is not self._packet_capture_connection
            ):
                return False
            self._finish_packet_capture_state()
            if safety_limit:
                self._status_message = (
                    "Packet capture stopped at the 15-minute safety limit"
                )
            self._publish_snapshot()
            return True

    def _cancel_packet_capture_watchdog(self) -> None:
        task = self._packet_capture_watchdog_task
        self._packet_capture_watchdog_task = None
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if task is not None and task is not current_task:
            task.cancel()

    def _finish_packet_capture_state(self) -> None:
        self._packet_capture_active = False
        self._packet_capture_connection = None
        self._packet_capture_generation += 1
        self._cancel_packet_capture_watchdog()

    async def submit_support_report(self, report: SupportReport) -> None:
        from proton.vpn.session.dataclasses import BugReportForm

        with TemporaryDirectory(prefix="proton-vpn-kde-support-") as directory:
            log_paths = (
                await asyncio.to_thread(collect_support_logs, Path(directory))
                if report.include_logs
                else []
            )
            with ExitStack() as attachments:
                report_form = BugReportForm(
                    username=report.username,
                    email=report.email,
                    title="Report from KDE Plasma app",
                    description=report.description,
                    client_version=__version__,
                    client="KDE Plasma GUI",
                    attachments=[
                        attachments.enter_context(path.open("rb")) for path in log_paths
                    ],
                )
                try:
                    await self._api.submit_bug_report(report_form)
                except Exception:
                    raise UserVisibleRuntimeError(
                        "Proton could not submit the issue report"
                    ) from None

    async def take_pending_nps_survey(self) -> bool:
        try:
            notifications = list(
                self._api.refresher.notifications.get_nps_survey_notifications()
            )
        except AttributeError:
            return False
        while notifications:
            survey = notifications.pop()
            if not survey.seen and survey.is_active:
                await asyncio.to_thread(
                    self._api.set_notification_seen, survey.survey_id
                )
                return True
        return False

    async def submit_nps_survey(self, response: NpsSurveyResponse) -> None:
        from proton.vpn.session.dataclasses import NPSSurveyResponse

        response_type = (
            NPSSurveyResponse.ResponseType.DISMISS
            if response.dismissed
            else NPSSurveyResponse.ResponseType.SUBMIT
        )
        try:
            await self._api.submit_nps_response(
                NPSSurveyResponse(
                    user_score=response.score,
                    user_comments=response.comments,
                    response_type=response_type,
                )
            )
        except Exception:
            raise UserVisibleRuntimeError(
                "Proton could not submit the survey response"
            ) from None

    async def _get_server_list(self):
        try:
            return await self._api.refresher.get_up_to_date_server_list()
        except Exception as error:
            await self._raise_session_error(error)

    @staticmethod
    def _countries(server_list):
        return server_list.group_by_country(
            group_by_location=True,
            include_free_servers=server_list.user_tier == 0,
        )

    def _country(self, server_list, country_code: str):
        for country in self._countries(server_list):
            if country.code.upper() == country_code:
                return country
        raise UserVisibleValueError(
            "The selected Proton country is no longer available"
        )

    def _server_group(
        self, server_list, country_code: str, group_kind: str, group_name: str
    ):
        country = self._country(server_list, country_code)
        if group_kind == "secure-core":
            group = country.secure_core_group
            if group is not None and group.name == group_name:
                return group
        elif group_kind == "location":
            for location in country.locations:
                if location.name == group_name:
                    return location
        raise UserVisibleValueError(
            "The selected Proton server group is no longer available"
        )

    @staticmethod
    def _server_info(server_list, server) -> ServerInfo:
        from proton.vpn.session.servers import ServerFeatureEnum

        available = list(
            server_list.get_available_servers([server], server_list.user_tier)
        )
        return ServerInfo(
            name=server.name,
            location=server.location or "",
            entry_country=server.entry_country.upper(),
            load=server.load or 0,
            accessible=bool(available),
            under_maintenance=server.under_maintenance,
            smart_routing=server.smart_routing,
            secure_core=ServerFeatureEnum.SECURE_CORE in server.features,
            tor=ServerFeatureEnum.TOR in server.features,
            p2p=ServerFeatureEnum.P2P in server.features,
            streaming=ServerFeatureEnum.STREAMING in server.features,
        )

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
        return VpnSettings(
            protocol=settings.protocol,
            protocols=self._available_protocols(settings.protocol),
            kill_switch=self._kill_switch,
            net_shield=int(settings.features.netshield),
            vpn_accelerator=bool(settings.features.vpn_accelerator),
            moderate_nat=bool(settings.features.moderate_nat),
            port_forwarding=bool(settings.features.port_forwarding),
            ipv6=bool(settings.ipv6),
            anonymous_crash_reports=bool(settings.anonymous_crash_reports),
            paid_features_available=self._user_tier() >= 1,
            protocol_editable=disconnected,
            kill_switch_editable=disconnected,
            split_tunneling_enabled=bool(settings.features.split_tunneling.enabled),
            custom_dns_enabled=bool(settings.custom_dns.enabled),
            packet_capture_supported=self._protocol_supports_packet_capture(
                settings.protocol
            ),
        )

    def _split_tunneling_from_core(self, settings: Any) -> SplitTunnelingSettings:
        split_tunneling = settings.features.split_tunneling
        return SplitTunnelingSettings(
            available=bool(self._connector.is_split_tunneling_available),
            paid_features_available=self._user_tier() >= 1,
            enabled=bool(split_tunneling.enabled),
            mode=self._mode_value(split_tunneling.mode),
            exclude_app_paths=tuple(split_tunneling.exclude.app_paths),
            include_app_paths=tuple(split_tunneling.include.app_paths),
            exclude_ip_ranges=tuple(
                str(ip_range) for ip_range in split_tunneling.exclude.ip_ranges
            ),
            include_ip_ranges=tuple(
                str(ip_range) for ip_range in split_tunneling.include.ip_ranges
            ),
        )

    def _custom_dns_from_core(self, settings: Any) -> CustomDnsSettings:
        return CustomDnsSettings(
            paid_features_available=self._user_tier() >= 1,
            enabled=bool(settings.custom_dns.enabled),
            servers=tuple(
                CustomDnsServer(
                    address=entry.ip.compressed,
                    enabled=bool(entry.enabled),
                )
                for entry in settings.custom_dns.ip_list
            ),
        )

    def _available_protocols(self, current_protocol: str) -> tuple[ProtocolInfo, ...]:
        protocols: list[ProtocolInfo] = []
        seen: set[str] = set()
        try:
            for candidate in self._iter_available_protocols():
                protocol_id = str(candidate.protocol)
                if protocol_id in seen:
                    continue
                seen.add(protocol_id)
                protocols.append(ProtocolInfo(protocol_id, str(candidate.ui_protocol)))
        except (AttributeError, TypeError):
            pass
        if current_protocol not in seen:
            protocols.append(ProtocolInfo(current_protocol, current_protocol))
        return tuple(protocols)

    def _user_tier(self) -> int:
        if not self._logged_in:
            return 0
        return int(self._api.account_data.max_tier)

    @staticmethod
    def _protocol_supports_split_tunneling(protocol: str) -> bool:
        return protocol == "wireguard" or protocol.startswith("protun-")

    def _protocol_supports_packet_capture(self, protocol: str) -> bool:
        try:
            for candidate in self._iter_available_protocols():
                if str(candidate.protocol) == protocol and bool(
                    candidate.supports_packet_capture()
                ):
                    return True
        except (AttributeError, TypeError):
            pass
        return False

    def _iter_available_protocols(self):
        groups = ["generic"]
        try:
            if self._api.refresher.feature_flags.get("ProTunV1"):
                groups.append("protun")
        except (AttributeError, TypeError):
            pass
        for group in groups:
            yield from self._connector.iter_available_protocols(group)

    @staticmethod
    def _connection_supports_packet_capture(connection: Any) -> bool:
        try:
            return bool(connection.supports_packet_capture())
        except (AttributeError, TypeError):
            return False

    @staticmethod
    def _mode_value(mode: Any) -> str:
        return str(getattr(mode, "value", mode))

    async def disconnect(self) -> None:
        await self._connector.disconnect()

    async def login(self, username: str, password: str) -> None:
        settings = await self._load_settings()
        self._kill_switch = self._kill_switch_value(settings)
        if self._kill_switch == 2:
            raise UserVisibleRuntimeError(
                "Disable the permanent kill switch before signing in"
            )
        self._auth_state = "signing_in"
        self._status_message = "Signing in…"
        self._publish_snapshot()
        try:
            result = await self._api.login(username, password)
        except Exception as error:
            self._handle_authentication_error(error)
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
            self._handle_authentication_error(error, fallback_state="two_factor")
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
            # A partially authenticated session may have no server-side session
            # left to revoke. Locally it must still return to signed-out state.
            pass
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
            assertion = await self._api.generate_2fa_fido2_assertion(
                interaction,
                interaction.cancel_assertion,
            )
            if interaction.cancelled:
                self._set_auth_status(
                    "two_factor", "Security-key authentication cancelled"
                )
                return
            result = await self._api.submit_2fa_fido2(assertion)
        except Exception as error:
            if interaction.cancelled:
                self._set_auth_status(
                    "two_factor", "Security-key authentication cancelled"
                )
            else:
                self._handle_fido2_error(error)
            return
        finally:
            self._fido_interaction = None

        if not result.success:
            self._set_auth_status("fido_error", "The security key was not accepted")
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
        await self.cancel_fido2()
        if type(self._connector.current_state).__name__ != "Disconnected":
            await self._connector.disconnect()
        settings = await self._load_settings()
        previous_kill_switch = self._kill_switch_value(settings)
        kill_switch_changed = previous_kill_switch != 0
        zero_kill_switch_persisted = False
        try:
            if kill_switch_changed:
                settings.killswitch = 0
                await self._save_settings(settings)
                zero_kill_switch_persisted = True
            self._kill_switch = 0
            if self._reconnector:
                await self._reconnector.disable()
            self._session_services_enabled = False
            await self._api.logout()
        except (Exception, asyncio.CancelledError) as error:
            rollback_failed = False
            if kill_switch_changed:
                settings.killswitch = previous_kill_switch
                self._kill_switch = previous_kill_switch
                try:
                    if zero_kill_switch_persisted:
                        await self._save_settings(settings)
                except (Exception, asyncio.CancelledError):
                    rollback_failed = True
            session_recovery_failed = False
            if self._logged_in:
                try:
                    await self._enable_session_services()
                except (Exception, asyncio.CancelledError):
                    session_recovery_failed = True
            if rollback_failed:
                raise UserVisibleRuntimeError(
                    "Sign-out failed and the kill switch setting could not be restored; review VPN settings before reconnecting"
                ) from None
            if session_recovery_failed:
                raise UserVisibleRuntimeError(
                    "Sign-out failed and the Proton session could not be restored"
                ) from None
            if isinstance(error, asyncio.CancelledError):
                raise
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
        if self._kill_switch_value(settings) != 0:
            settings.killswitch = 0
            await self._save_settings(settings)
        self._kill_switch = 0
        self._status_message = "Kill switch disabled; you can now sign in"
        self._publish_snapshot()

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        self._reconnection_enabled = enabled
        if not self._reconnector:
            return
        if enabled:
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
        self._cancel_packet_capture_watchdog()
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
        self._logged_in = True
        self._auth_state = "signed_in"
        self._status_message = ""
        await self._enable_session_services()
        self._publish_snapshot()

    async def _enable_session_services(self) -> None:
        if not self._session_services_enabled:
            await self._api.refresher.enable()
            self._session_services_enabled = True
        if not self._reconnector:
            self._reconnector = AsyncReconnector(
                self._connector,
                self._api.refresher,
                self._on_reconnector_status,
            )
        if self._reconnection_enabled:
            self._reconnector.enable()

    async def _set_signed_out(
        self, message: str, auth_state: str = "signed_out"
    ) -> None:
        self._logged_in = False
        self._auth_state = auth_state
        self._status_message = message
        self._session_services_enabled = False
        self._search_projection = None
        self._publish_snapshot()

    async def _raise_session_error(self, error: Exception):
        if type(error).__name__ != "ProtonAPIAuthenticationNeeded":
            raise error
        if self._reconnector:
            await self._reconnector.disable()
        if self._session_services_enabled:
            await self._api.refresher.disable()
        await self._set_signed_out(
            "Your Proton session expired; sign in again",
            auth_state="expired",
        )
        raise UserVisibleRuntimeError(
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
        state_name = type(state).__name__.lower() if state else "unavailable"
        allowed_states = {
            "connected",
            "connecting",
            "disconnecting",
            "disconnected",
            "error",
        }
        if state_name not in allowed_states:
            state_name = "error"
        if state_name != "connected":
            if self._packet_capture_active or self._packet_capture_watchdog_task:
                self._finish_packet_capture_state()

        error_code = ""
        if state_name == "error":
            event = getattr(getattr(state, "context", None), "event", None)
            error_code = {
                "TunnelSetupFailed": "tunnel_setup_failed",
                "AuthDenied": "authentication_denied",
                "Timeout": "timeout",
                "DeviceDisconnected": "device_disconnected",
                "MaximumSessionsReached": "maximum_sessions_reached",
                "ExpiredCertificate": "certificate_expired",
                "NotYetValidCertificate": "certificate_not_yet_valid",
                "TwoFARequired": "two_factor_required",
                "UnexpectedError": "unexpected_error",
            }.get(type(event).__name__, "unexpected_error")

        connection = self._connector.current_connection if self._connector else None
        server_name = connection.server_name if connection else ""
        logical_server = None
        if server_name and self._logged_in:
            try:
                logical_server = self._api.refresher.server_list.get_by_name(
                    server_name
                )
            except Exception:
                logical_server = None
        forwarded_port = 0
        if state_name == "connected":
            try:
                candidate_port = state.forwarded_port
                if type(candidate_port) is int and 0 < candidate_port <= 65535:
                    forwarded_port = candidate_port
            except Exception:
                forwarded_port = 0
        server_location = ""
        exit_country = ""
        entry_country = ""
        secure_core = False
        tor = False
        p2p = False
        streaming = False
        smart_routing = False
        if logical_server is not None:
            from proton.vpn.session.servers import ServerFeatureEnum

            server_location = logical_server.location or ""
            exit_country = logical_server.exit_country.upper()
            entry_country = logical_server.entry_country.upper()
            secure_core = ServerFeatureEnum.SECURE_CORE in logical_server.features
            tor = ServerFeatureEnum.TOR in logical_server.features
            p2p = ServerFeatureEnum.P2P in logical_server.features
            streaming = ServerFeatureEnum.STREAMING in logical_server.features
            smart_routing = logical_server.smart_routing
        account_name = ""
        plan_title = ""
        user_tier = 0
        max_connections = 0
        if self._logged_in:
            account_name = self._api.account_name or ""
            account = self._api.account_data
            plan_title = account.plan_title or "Free"
            user_tier = account.max_tier
            max_connections = account.max_connections
        return VpnSnapshot(
            ready=True,
            startup_compatible=self._startup_compatible,
            logged_in=self._logged_in,
            auth_state=self._auth_state,
            account_name=account_name,
            plan_title=plan_title,
            user_tier=user_tier,
            max_connections=max_connections,
            fido2_available=(
                not self._logged_in
                and self._auth_state
                in {
                    "two_factor",
                    "fido_waiting",
                    "fido_touch",
                    "fido_select",
                    "fido_pin",
                    "fido_error",
                }
                and bool(self._api.supports_fido2)
            ),
            reconnect_enabled=self._reconnection_enabled,
            kill_switch=self._kill_switch,
            state=state_name,
            error_code=error_code,
            server_name=server_name,
            server_location=server_location,
            exit_country=exit_country,
            entry_country=entry_country,
            forwarded_port=forwarded_port,
            secure_core=secure_core,
            tor=tor,
            p2p=p2p,
            streaming=streaming,
            smart_routing=smart_routing,
            packet_capture_active=self._packet_capture_active,
            core_memory_optimized=self._core_memory_optimized,
            core_version=self._core_version,
            message=(
                self._status_message
                if self._logged_in
                else self._status_message or "Sign in to Proton VPN to continue"
            ),
        )

    @staticmethod
    def _kill_switch_value(settings: Any) -> int:
        try:
            value = int(settings.killswitch)
        except (AttributeError, TypeError, ValueError):
            return 0
        return value if value in {0, 1, 2} else 0
