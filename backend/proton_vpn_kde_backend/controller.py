"""Desktop-neutral VPN state controller."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import asdict, dataclass, replace
from ipaddress import ip_address, ip_network
import json
import logging
import re
from typing import Callable, Protocol, TypeAlias, TypeVar

from .errors import UserVisibleRuntimeError, UserVisibleValueError


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VpnSnapshot:
    """Non-sensitive state exposed to frontend processes."""

    schema_version: int = 1
    ready: bool = False
    startup_compatible: bool = True
    logged_in: bool = False
    auth_state: str = "signed_out"
    account_name: str = ""
    plan_title: str = ""
    user_tier: int = 0
    max_connections: int = 0
    fido2_available: bool = False
    reconnect_enabled: bool = True
    kill_switch: int = 0
    busy: bool = False
    state: str = "starting"
    error_code: str = ""
    server_name: str = ""
    server_location: str = ""
    exit_country: str = ""
    entry_country: str = ""
    forwarded_port: int = 0
    secure_core: bool = False
    tor: bool = False
    p2p: bool = False
    streaming: bool = False
    smart_routing: bool = False
    packet_capture_active: bool = False
    core_memory_optimized: bool = False
    core_version: str = ""
    message: str = ""

    def to_json(self) -> str:
        payload = asdict(self)
        payload["schemaVersion"] = payload.pop("schema_version")
        payload["startupCompatible"] = payload.pop("startup_compatible")
        payload["loggedIn"] = payload.pop("logged_in")
        payload["authState"] = payload.pop("auth_state")
        payload["accountName"] = payload.pop("account_name")
        payload["planTitle"] = payload.pop("plan_title")
        payload["userTier"] = payload.pop("user_tier")
        payload["maxConnections"] = payload.pop("max_connections")
        payload["fido2Available"] = payload.pop("fido2_available")
        payload["reconnectEnabled"] = payload.pop("reconnect_enabled")
        payload["killSwitch"] = payload.pop("kill_switch")
        payload["errorCode"] = payload.pop("error_code")
        payload["serverName"] = payload.pop("server_name")
        payload["serverLocation"] = payload.pop("server_location")
        payload["exitCountry"] = payload.pop("exit_country")
        payload["entryCountry"] = payload.pop("entry_country")
        payload["forwardedPort"] = payload.pop("forwarded_port")
        payload["secureCore"] = payload.pop("secure_core")
        payload["smartRouting"] = payload.pop("smart_routing")
        payload["packetCaptureActive"] = payload.pop("packet_capture_active")
        payload["coreMemoryOptimized"] = payload.pop("core_memory_optimized")
        payload["coreVersion"] = payload.pop("core_version")
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True, slots=True)
class CountryInfo:
    code: str
    server_count: int
    accessible: bool = True
    under_maintenance: bool = False
    free: bool = False


@dataclass(frozen=True, slots=True)
class ServerGroupInfo:
    kind: str
    name: str
    server_count: int
    accessible: bool = True
    under_maintenance: bool = False
    smart_routing: bool = False
    secure_core: bool = False
    tor: bool = False
    p2p: bool = False
    streaming: bool = False


@dataclass(frozen=True, slots=True)
class ServerInfo:
    name: str
    location: str = ""
    load: int = 0
    p2p: bool = False
    streaming: bool = False
    entry_country: str = ""
    accessible: bool = True
    under_maintenance: bool = False
    smart_routing: bool = False
    secure_core: bool = False
    tor: bool = False


@dataclass(frozen=True, slots=True)
class ServerLoadInfo:
    name: str
    load: int


@dataclass(frozen=True, slots=True)
class LocationSearchInfo:
    kind: str
    name: str
    country_code: str
    location: str = ""
    group_kind: str = "location"
    group_name: str = ""
    load: int = -1
    accessible: bool = True
    under_maintenance: bool = False


@dataclass(frozen=True, slots=True)
class ProtocolInfo:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class VpnSettings:
    """Validated, non-sensitive subset of Proton's persisted settings."""

    schema_version: int = 1
    protocol: str = "wireguard"
    protocols: tuple[ProtocolInfo, ...] = ()
    kill_switch: int = 0
    net_shield: int = 0
    vpn_accelerator: bool = True
    moderate_nat: bool = False
    port_forwarding: bool = False
    ipv6: bool = True
    anonymous_crash_reports: bool = True
    paid_features_available: bool = False
    protocol_editable: bool = True
    kill_switch_editable: bool = True
    split_tunneling_enabled: bool = False
    custom_dns_enabled: bool = False
    packet_capture_supported: bool = False

    def to_json(self) -> str:
        payload = {
            "schemaVersion": self.schema_version,
            "protocol": self.protocol,
            "protocols": [asdict(item) for item in self.protocols],
            "killSwitch": self.kill_switch,
            "netShield": self.net_shield,
            "vpnAccelerator": self.vpn_accelerator,
            "moderateNat": self.moderate_nat,
            "portForwarding": self.port_forwarding,
            "ipv6": self.ipv6,
            "anonymousCrashReports": self.anonymous_crash_reports,
            "paidFeaturesAvailable": self.paid_features_available,
            "protocolEditable": self.protocol_editable,
            "killSwitchEditable": self.kill_switch_editable,
            "splitTunnelingEnabled": self.split_tunneling_enabled,
            "customDnsEnabled": self.custom_dns_enabled,
            "packetCaptureSupported": self.packet_capture_supported,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True, slots=True)
class SplitTunnelingSettings:
    """Validated view of Proton core's split-tunneling configuration."""

    schema_version: int = 1
    available: bool = False
    paid_features_available: bool = False
    enabled: bool = False
    mode: str = "exclude"
    exclude_app_paths: tuple[str, ...] = ()
    include_app_paths: tuple[str, ...] = ()
    exclude_ip_ranges: tuple[str, ...] = ()
    include_ip_ranges: tuple[str, ...] = ()

    def to_json(self) -> str:
        return json.dumps(
            {
                "schemaVersion": self.schema_version,
                "available": self.available,
                "paidFeaturesAvailable": self.paid_features_available,
                "enabled": self.enabled,
                "mode": self.mode,
                "excludeAppPaths": list(self.exclude_app_paths),
                "includeAppPaths": list(self.include_app_paths),
                "excludeIpRanges": list(self.exclude_ip_ranges),
                "includeIpRanges": list(self.include_ip_ranges),
                "excludeIpRangeCount": len(self.exclude_ip_ranges),
                "includeIpRangeCount": len(self.include_ip_ranges),
            },
            separators=(",", ":"),
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class CustomDnsServer:
    """One Proton core custom-DNS entry."""

    address: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class CustomDnsSettings:
    """Validated view of Proton core's custom-DNS configuration."""

    schema_version: int = 1
    paid_features_available: bool = False
    enabled: bool = False
    servers: tuple[CustomDnsServer, ...] = ()

    def to_json(self) -> str:
        return json.dumps(
            {
                "schemaVersion": self.schema_version,
                "paidFeaturesAvailable": self.paid_features_available,
                "enabled": self.enabled,
                "servers": [asdict(server) for server in self.servers],
            },
            separators=(",", ":"),
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class SupportReport:
    """Validated user-supplied Proton support request."""

    username: str
    email: str
    description: str
    include_logs: bool = True


@dataclass(frozen=True, slots=True)
class NpsSurveyResponse:
    score: int = 0
    comments: str = ""
    dismissed: bool = False


_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]{2,}\.[^@\s.\-]{2,}")


def validate_support_report(
    username: str,
    email: str,
    description: str,
    include_logs: str,
) -> SupportReport:
    """Bound and validate fields received through the protected payload."""
    normalized_username = username.strip()
    normalized_email = email.strip()
    normalized_description = description.strip()
    if (
        not normalized_username
        or len(normalized_username) > 255
        or "\0" in normalized_username
    ):
        raise UserVisibleValueError("Enter your Proton username")
    if (
        len(normalized_email) > 254
        or "\0" in normalized_email
        or _EMAIL_PATTERN.fullmatch(normalized_email) is None
    ):
        raise UserVisibleValueError("Enter a valid email address")
    if "\0" in normalized_description or len(normalized_description) < 50:
        raise UserVisibleValueError("Describe the issue using at least 50 characters")
    if len(normalized_description) > 8000:
        raise UserVisibleValueError("The issue description is too long")
    if include_logs not in {"true", "false"}:
        raise UserVisibleValueError("The support-report log choice is invalid")
    return SupportReport(
        username=normalized_username,
        email=normalized_email,
        description=normalized_description,
        include_logs=include_logs == "true",
    )


def validate_nps_survey_response(
    score: str, comments: str, response_type: str
) -> NpsSurveyResponse:
    if response_type not in {"submit", "dismiss"}:
        raise UserVisibleValueError("The survey response type is invalid")
    if response_type == "dismiss":
        return NpsSurveyResponse(dismissed=True)
    try:
        numeric_score = int(score)
    except ValueError as error:
        raise UserVisibleValueError("Select a survey score") from error
    if numeric_score < 0 or numeric_score > 10:
        raise UserVisibleValueError("Select a survey score from 0 through 10")
    if len(comments) > 250 or "\0" in comments:
        raise UserVisibleValueError("The survey feedback is too long")
    return NpsSurveyResponse(score=numeric_score, comments=comments)


SettingsValue: TypeAlias = str | int | bool
SplitTunnelingValue: TypeAlias = bool | str | list[str]
CustomDnsServerValue: TypeAlias = dict[str, str | bool]
CustomDnsValue: TypeAlias = bool | list[CustomDnsServerValue]

_SETTING_TYPES: dict[str, type[str] | type[int] | type[bool]] = {
    "protocol": str,
    "killSwitch": int,
    "netShield": int,
    "vpnAccelerator": bool,
    "moderateNat": bool,
    "portForwarding": bool,
    "ipv6": bool,
    "anonymousCrashReports": bool,
}


def settings_patch_from_json(patch_json: str) -> dict[str, SettingsValue]:
    if not patch_json or len(patch_json) > 4096:
        raise UserVisibleValueError("The settings update is empty or too large")
    try:
        payload = json.loads(patch_json)
    except json.JSONDecodeError as error:
        raise UserVisibleValueError("The settings update is not valid JSON") from error
    if not isinstance(payload, dict) or not payload:
        raise UserVisibleValueError("The settings update must be a non-empty object")
    unknown = set(payload) - set(_SETTING_TYPES)
    if unknown:
        raise UserVisibleValueError("The settings update contains an unsupported field")
    for key, value in payload.items():
        expected_type = _SETTING_TYPES[key]
        if type(value) is not expected_type:
            raise UserVisibleValueError(f"The {key} setting has the wrong value type")
    if "protocol" in payload:
        protocol = payload["protocol"]
        if (
            not isinstance(protocol, str)
            or not protocol
            or len(protocol) > 64
            or not protocol.isascii()
        ):
            raise UserVisibleValueError("Select a valid VPN protocol")
    if "killSwitch" in payload and payload["killSwitch"] not in {0, 1, 2}:
        raise UserVisibleValueError("Select a valid kill-switch mode")
    if "netShield" in payload and payload["netShield"] not in {0, 1, 2}:
        raise UserVisibleValueError("Select a valid NetShield mode")
    return payload


_SPLIT_TUNNELING_TYPES: dict[str, type[bool] | type[str] | type[list]] = {
    "enabled": bool,
    "mode": str,
    "excludeAppPaths": list,
    "includeAppPaths": list,
    "excludeIpRanges": list,
    "includeIpRanges": list,
}
_FORBIDDEN_SPLIT_TUNNELING_COMMANDS = {
    "/",
    "/app",
    "/bin",
    "/snap",
    "/usr",
    "/usr/bin",
}


def split_tunneling_patch_from_json(
    patch_json: str,
) -> dict[str, SplitTunnelingValue]:
    if not patch_json or len(patch_json) > 65536:
        raise UserVisibleValueError("The split-tunneling update is empty or too large")
    try:
        payload = json.loads(patch_json)
    except json.JSONDecodeError as error:
        raise UserVisibleValueError(
            "The split-tunneling update is not valid JSON"
        ) from error
    if not isinstance(payload, dict) or not payload:
        raise UserVisibleValueError(
            "The split-tunneling update must be a non-empty object"
        )
    unknown = set(payload) - set(_SPLIT_TUNNELING_TYPES)
    if unknown:
        raise UserVisibleValueError(
            "The split-tunneling update contains an unsupported field"
        )
    for key, value in payload.items():
        if type(value) is not _SPLIT_TUNNELING_TYPES[key]:
            raise UserVisibleValueError(
                f"The {key} split-tunneling value has the wrong type"
            )
    if "mode" in payload and payload["mode"] not in {"exclude", "include"}:
        raise UserVisibleValueError("Select a valid split-tunneling mode")
    for key in ("excludeAppPaths", "includeAppPaths"):
        if key not in payload:
            continue
        app_paths = payload[key]
        if not isinstance(app_paths, list) or len(app_paths) > 256:
            raise UserVisibleValueError(
                "Too many split-tunneling applications were selected"
            )
        seen: set[str] = set()
        for path in app_paths:
            if (
                type(path) is not str
                or not path
                or len(path) > 4096
                or "\0" in path
                or "\n" in path
                or "\r" in path
                or path != path.strip()
            ):
                raise UserVisibleValueError(
                    "A split-tunneling application path is invalid"
                )
            command = path.split(maxsplit=1)[0].rstrip("/") or "/"
            if command in _FORBIDDEN_SPLIT_TUNNELING_COMMANDS:
                raise UserVisibleValueError("Select a specific application executable")
            lowered = command.casefold()
            if "proton-vpn-kde" in lowered or "protonvpn-app" in lowered:
                raise UserVisibleValueError(
                    "The Proton VPN client cannot bypass its own tunnel"
                )
            if path in seen:
                raise UserVisibleValueError(
                    "A split-tunneling application was selected twice"
                )
            seen.add(path)
    for key in ("excludeIpRanges", "includeIpRanges"):
        if key not in payload:
            continue
        ranges = payload[key]
        if not isinstance(ranges, list) or len(ranges) > 256:
            raise UserVisibleValueError(
                "Too many split-tunneling IP ranges were selected"
            )
        normalized_ranges: list[str] = []
        seen_ranges: set[str] = set()
        for value in ranges:
            if (
                type(value) is not str
                or not value
                or len(value) > 64
                or value != value.strip()
            ):
                raise UserVisibleValueError("A split-tunneling IP range is invalid")
            try:
                normalized = ip_network(value, strict=False).with_prefixlen
            except ValueError as error:
                raise UserVisibleValueError(
                    "Enter a valid IPv4 or IPv6 address or CIDR range"
                ) from error
            if normalized in seen_ranges:
                raise UserVisibleValueError(
                    "A split-tunneling IP range was selected twice"
                )
            seen_ranges.add(normalized)
            normalized_ranges.append(normalized)
        payload[key] = normalized_ranges
    return payload


_CUSTOM_DNS_TYPES: dict[str, type[bool] | type[list]] = {
    "enabled": bool,
    "servers": list,
}


def custom_dns_patch_from_json(
    patch_json: str,
) -> dict[str, CustomDnsValue]:
    if not patch_json or len(patch_json) > 65536:
        raise UserVisibleValueError("The custom-DNS update is empty or too large")
    try:
        payload = json.loads(patch_json)
    except json.JSONDecodeError as error:
        raise UserVisibleValueError(
            "The custom-DNS update is not valid JSON"
        ) from error
    if not isinstance(payload, dict) or not payload:
        raise UserVisibleValueError("The custom-DNS update must be a non-empty object")
    unknown = set(payload) - set(_CUSTOM_DNS_TYPES)
    if unknown:
        raise UserVisibleValueError(
            "The custom-DNS update contains an unsupported field"
        )
    for key, value in payload.items():
        if type(value) is not _CUSTOM_DNS_TYPES[key]:
            raise UserVisibleValueError(
                f"The {key} custom-DNS value has the wrong type"
            )

    if "servers" not in payload:
        return payload

    servers = payload["servers"]
    if not isinstance(servers, list) or len(servers) > 256:
        raise UserVisibleValueError("Too many custom DNS servers were provided")
    normalized_servers: list[CustomDnsServerValue] = []
    for server in servers:
        if type(server) is not dict or set(server) != {"address", "enabled"}:
            raise UserVisibleValueError("A custom DNS server entry is invalid")
        address = server["address"]
        entry_enabled = server["enabled"]
        if type(address) is not str or type(entry_enabled) is not bool:
            raise UserVisibleValueError("A custom DNS server entry is invalid")
        if not address or len(address) > 64 or address != address.strip():
            raise UserVisibleValueError("Enter a valid IPv4 or IPv6 DNS server address")
        try:
            normalized_address = ip_address(address).compressed
        except ValueError as error:
            raise UserVisibleValueError(
                "Enter a valid IPv4 or IPv6 DNS server address"
            ) from error
        normalized_servers.append(
            {"address": normalized_address, "enabled": entry_enabled}
        )
    payload["servers"] = normalized_servers
    return payload


LocationInfo = TypeVar(
    "LocationInfo",
    CountryInfo,
    ServerGroupInfo,
    ServerInfo,
    ServerLoadInfo,
    LocationSearchInfo,
)


def location_list_to_json(kind: str, items: list[LocationInfo]) -> str:
    payload_items = []
    for item in items:
        payload = asdict(item)
        for internal_name, external_name in (
            ("server_count", "serverCount"),
            ("country_code", "countryCode"),
            ("group_kind", "groupKind"),
            ("group_name", "groupName"),
            ("entry_country", "entryCountry"),
            ("under_maintenance", "underMaintenance"),
            ("smart_routing", "smartRouting"),
            ("secure_core", "secureCore"),
        ):
            if internal_name in payload:
                payload[external_name] = payload.pop(internal_name)
        payload_items.append(payload)
    return json.dumps(
        {"schemaVersion": 1, kind: payload_items},
        separators=(",", ":"),
        sort_keys=True,
    )


SnapshotCallback = Callable[[VpnSnapshot], None]
ServerDataCallback = Callable[[bool], None]
SettingsCallback = Callable[[VpnSettings], None]
SplitTunnelingCallback = Callable[[SplitTunnelingSettings], None]
CustomDnsCallback = Callable[[CustomDnsSettings], None]


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
    async def connect_country(self, country_code: str) -> None: ...
    async def connect_group(
        self, country_code: str, group_kind: str, group_name: str
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

    def __init__(self, adapter: CoreAdapter):
        self._adapter = adapter
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
