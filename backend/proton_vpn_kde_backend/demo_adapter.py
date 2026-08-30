# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Deterministic VPN adapter for tests, demos, and visual development."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

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
from .errors import UserVisibleRuntimeError, UserVisibleValueError
from .search_projection import fold_search_text


def _supports_split_tunneling(protocol: str) -> bool:
    return protocol == "wireguard" or protocol.startswith("protun-")


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
