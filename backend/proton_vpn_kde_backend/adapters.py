"""Proton core and safe demo backend adapters."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

from .controller import (
    CountryInfo,
    CustomDnsServer,
    CustomDnsSettings,
    CustomDnsValue,
    ProtocolInfo,
    ServerDataCallback,
    ServerInfo,
    ServerLoadInfo,
    SplitTunnelingSettings,
    SplitTunnelingValue,
    SettingsValue,
    SnapshotCallback,
    VpnSettings,
    VpnSnapshot,
)
from .fido_interaction import FidoInteraction
from .reconnector import AsyncReconnector


def _supports_split_tunneling(protocol: str) -> bool:
    return protocol == "wireguard" or protocol.startswith("protun-")


class DemoCoreAdapter:
    """Deterministic adapter that never touches the network or credentials."""

    def __init__(self, logged_in: bool = True):
        self._callback: SnapshotCallback | None = None
        self._server_data_callback: ServerDataCallback | None = None
        self._logged_in = logged_in
        self._auth_state = "signed_in" if logged_in else "signed_out"
        self._reconnection_enabled = True
        self._settings = VpnSettings(
            protocols=(
                ProtocolInfo("wireguard", "WireGuard"),
                ProtocolInfo("openvpn-udp", "OpenVPN (UDP)"),
                ProtocolInfo("openvpn-tcp", "OpenVPN (TCP)"),
            ),
            paid_features_available=logged_in,
        )
        self._split_tunneling = SplitTunnelingSettings(
            available=True,
            paid_features_available=logged_in,
        )
        self._custom_dns = CustomDnsSettings(
            paid_features_available=logged_in,
        )
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
        await self._transition("connecting", "")
        await asyncio.sleep(0.15)
        await self._transition("connected", "US-IL#600")

    async def get_countries(self) -> list[CountryInfo]:
        return [CountryInfo("CH", 3), CountryInfo("US", 5)]

    async def get_servers(self, country_code: str) -> list[ServerInfo]:
        demo_servers = {
            "CH": [
                ServerInfo("CH#101", "Zurich", 24, p2p=True),
                ServerInfo("CH#202", "Zurich", 51, streaming=True),
            ],
            "US": [
                ServerInfo("US-IL#600", "Chicago, IL", 32, p2p=True),
                ServerInfo("US-NY#88", "New York, NY", 47, streaming=True),
            ],
        }
        return demo_servers.get(country_code, [])

    async def get_server_loads(self, country_code: str) -> list[ServerLoadInfo]:
        return [
            ServerLoadInfo(server.name, server.load)
            for server in await self.get_servers(country_code)
        ]

    async def get_settings(self) -> VpnSettings:
        return replace(
            self._settings,
            paid_features_available=self._logged_in,
            protocol_editable=self._snapshot.state == "disconnected",
            kill_switch_editable=self._snapshot.state == "disconnected",
        )

    async def update_settings(
        self, patch: dict[str, SettingsValue]
    ) -> VpnSettings:
        if (
            self._snapshot.state != "disconnected"
            and ({"protocol", "killSwitch"} & set(patch))
        ):
            raise RuntimeError(
                "Disconnect the VPN before changing protocol or kill switch"
            )
        if not self._logged_in and (
            {"netShield", "vpnAccelerator", "moderateNat", "portForwarding"}
            & set(patch)
        ):
            raise RuntimeError("This setting requires a paid Proton VPN plan")
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
            raise ValueError("Select an available VPN protocol")
        self._settings = replace(self._settings, **replacements)
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
            raise RuntimeError("A Proton account session is required")
        if not self._split_tunneling.available:
            raise RuntimeError("Split tunneling is unavailable on this system")
        if patch.get("enabled") is True:
            if self._settings.kill_switch != 0:
                raise ValueError("Disable the kill switch before enabling split tunneling")
            if not _supports_split_tunneling(self._settings.protocol):
                raise ValueError("Select WireGuard or a compatible protocol first")

        replacements = {
            {
                "enabled": "enabled",
                "mode": "mode",
                "excludeAppPaths": "exclude_app_paths",
                "includeAppPaths": "include_app_paths",
            }[key]: tuple(value) if isinstance(value, list) else value
            for key, value in patch.items()
        }
        updated = replace(self._split_tunneling, **replacements)
        if (
            updated.enabled
            and updated.mode == "include"
            and not updated.include_app_paths
            and updated.include_ip_range_count == 0
        ):
            raise ValueError(
                "Select at least one included application before enabling this mode"
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
            raise RuntimeError("A Proton account session is required")
        final_enabled = patch.get("enabled", self._custom_dns.enabled)
        if final_enabled and self._settings.net_shield != 0:
            raise ValueError("Disable NetShield before enabling custom DNS")
        replacements: dict[str, Any] = {}
        if "enabled" in patch:
            replacements["enabled"] = bool(patch["enabled"])
        if "servers" in patch:
            replacements["servers"] = tuple(
                CustomDnsServer(
                    address=str(server["address"]),
                    enabled=bool(server["enabled"]),
                )
                for server in patch["servers"]
                if isinstance(server, dict)
            )
        self._custom_dns = replace(self._custom_dns, **replacements)
        self._settings = replace(
            self._settings,
            custom_dns_enabled=self._custom_dns.enabled,
        )
        return await self.get_custom_dns()

    async def connect_country(self, country_code: str) -> None:
        await self._transition("connecting", "")
        await asyncio.sleep(0.15)
        await self._transition("connected", f"{country_code}#FASTEST")

    async def connect_server(self, server_name: str) -> None:
        await self._transition("connecting", server_name)
        await asyncio.sleep(0.15)
        await self._transition("connected", server_name)

    async def disconnect(self) -> None:
        await self._transition("disconnecting", self._snapshot.server_name)
        await asyncio.sleep(0.1)
        await self._transition("disconnected", "")

    async def login(self, username: str, password: str) -> None:
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
        raise RuntimeError("Security-key authentication is unavailable in demo mode")

    async def submit_fido2_pin(self, pin: str) -> None:
        del pin
        raise RuntimeError("No security key is waiting for a PIN")

    async def cancel_fido2(self) -> None:
        return None

    async def logout(self) -> None:
        if self._snapshot.state != "disconnected":
            await self.disconnect()
        self._logged_in = False
        self._auth_state = "signed_out"
        self._publish(self._build_snapshot(message="Signed out"))

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
        return VpnSnapshot(
            ready=True,
            logged_in=self._logged_in,
            auth_state=self._auth_state,
            account_name=account_name if self._logged_in else "",
            plan_title="VPN Plus" if self._logged_in else "",
            user_tier=2 if self._logged_in else 0,
            max_connections=10 if self._logged_in else 0,
            reconnect_enabled=self._reconnection_enabled,
            state=state,
            server_name=server_name,
            message=message,
        )

    def _publish(self, snapshot: VpnSnapshot) -> None:
        self._snapshot = snapshot
        if self._callback:
            self._callback(self._snapshot)


class ProtonCoreAdapter:
    """Thin adapter over the official python-proton-vpn-api-core package.

    Proton modules are imported lazily so demo mode and unit tests have no
    dependency on a locally installed Proton client.
    """

    def __init__(self, api: Any = None):
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

    async def initialize(
        self,
        callback: SnapshotCallback,
        server_data_callback: ServerDataCallback | None = None,
    ) -> VpnSnapshot:
        self._callback = callback
        self._server_data_callback = server_data_callback
        if self._api is None:
            from proton.vpn.core.api import ProtonVPNAPI
            from proton.vpn.core.session_holder import ClientTypeMetadata

            self._api = ProtonVPNAPI(ClientTypeMetadata(type="gui"))

        # Proton SSO reaches Secret Service through a synchronous keyring API.
        # Warm the cached session away from the D-Bus asyncio thread so a
        # provider unlock prompt (KeePassXC, KWallet, etc.) cannot freeze the
        # entire backend while waiting for user approval.
        self._logged_in = await asyncio.to_thread(self._api.is_user_logged_in)
        self._auth_state = "signed_in" if self._logged_in else "signed_out"
        self._connector = await self._api.get_vpn_connector()
        self._connector.register(self)
        self._api.refresher.set_server_list_updated_callback(
            self._on_server_list_updated
        )
        self._api.refresher.set_server_loads_updated_callback(
            self._on_server_loads_updated
        )

        if self._logged_in:
            await self._enable_session_services()

        return self._snapshot_from_state(self._connector.current_state)

    async def connect_fastest(self) -> None:
        server_list = await self._get_server_list()
        logical_server = server_list.get_fastest()
        await self._connect_logical(logical_server)

    async def get_countries(self) -> list[CountryInfo]:
        server_list = await self._get_server_list()
        counts: dict[str, int] = {}
        for server in self._normal_servers(server_list):
            code = server.exit_country.upper()
            counts[code] = counts.get(code, 0) + 1
        return [CountryInfo(code, counts[code]) for code in sorted(counts)]

    async def get_servers(self, country_code: str) -> list[ServerInfo]:
        from proton.vpn.session.servers import ServerFeatureEnum

        server_list = await self._get_server_list()
        servers = (
            server
            for server in self._normal_servers(server_list)
            if server.exit_country.upper() == country_code
        )
        return [
            ServerInfo(
                name=server.name,
                location=server.location or "",
                load=server.load or 0,
                p2p=ServerFeatureEnum.P2P in server.features,
                streaming=ServerFeatureEnum.STREAMING in server.features,
            )
            for server in sorted(
                servers,
                key=lambda item: (item.load or 0, item.name),
            )
        ]

    async def get_server_loads(self, country_code: str) -> list[ServerLoadInfo]:
        server_list = await self._get_server_list()
        return [
            ServerLoadInfo(server.name, server.load or 0)
            for server in self._normal_servers(server_list)
            if server.exit_country.upper() == country_code
        ]

    async def get_settings(self) -> VpnSettings:
        settings = await self._load_settings()
        return self._settings_from_core(settings)

    async def get_split_tunneling(self) -> SplitTunnelingSettings:
        settings = await self._load_settings()
        return self._split_tunneling_from_core(settings)

    async def get_custom_dns(self) -> CustomDnsSettings:
        settings = await self._load_settings()
        return self._custom_dns_from_core(settings)

    async def update_settings(
        self, patch: dict[str, SettingsValue]
    ) -> VpnSettings:
        settings = await self._load_settings()
        state_name = type(self._connector.current_state).__name__.lower()
        if state_name != "disconnected" and (
            {"protocol", "killSwitch"} & set(patch)
        ):
            raise RuntimeError(
                "Disconnect the VPN before changing protocol or kill switch"
            )

        paid_fields = {
            "netShield",
            "vpnAccelerator",
            "moderateNat",
            "portForwarding",
        }
        if self._user_tier() < 1 and paid_fields & set(patch):
            raise RuntimeError("This setting requires a paid Proton VPN plan")

        protocols = {item.id for item in self._available_protocols(settings.protocol)}
        requested_protocol = patch.get("protocol")
        if requested_protocol is not None and requested_protocol not in protocols:
            raise ValueError("Select an available VPN protocol")

        split_tunneling_enabled = bool(settings.features.split_tunneling.enabled)
        if (
            split_tunneling_enabled
            and patch.get("killSwitch", settings.killswitch) != 0
        ):
            raise ValueError(
                "Disable split tunneling before enabling the kill switch"
            )
        if (
            split_tunneling_enabled
            and requested_protocol is not None
            and not self._protocol_supports_split_tunneling(requested_protocol)
        ):
            raise ValueError(
                "Disable split tunneling before selecting this protocol"
            )
        if (
            bool(settings.custom_dns.enabled)
            and patch.get("netShield", settings.features.netshield) != 0
        ):
            raise ValueError("Disable custom DNS before enabling NetShield")

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
            raise RuntimeError("Split tunneling is unavailable on this system")
        if self._user_tier() < 1:
            raise RuntimeError("Split tunneling requires a paid Proton VPN plan")

        final_enabled = patch.get("enabled", split_tunneling.enabled)
        final_mode = patch.get(
            "mode", self._mode_value(split_tunneling.mode)
        )
        if final_enabled:
            if int(settings.killswitch) != 0:
                raise ValueError("Disable the kill switch before enabling split tunneling")
            if not self._protocol_supports_split_tunneling(settings.protocol):
                raise ValueError("Select WireGuard or a compatible protocol first")
            if final_mode == "include":
                include_paths = patch.get(
                    "includeAppPaths", split_tunneling.include.app_paths
                )
                if not include_paths and not split_tunneling.include.ip_ranges:
                    raise ValueError(
                        "Select at least one included application before enabling this mode"
                    )

        if "mode" in patch:
            from proton.vpn.core.settings.split_tunneling import SplitTunnelingMode

            split_tunneling.mode = SplitTunnelingMode(patch["mode"])
        if "excludeAppPaths" in patch:
            split_tunneling.exclude.app_paths = list(patch["excludeAppPaths"])
        if "includeAppPaths" in patch:
            split_tunneling.include.app_paths = list(patch["includeAppPaths"])
        if "enabled" in patch:
            split_tunneling.enabled = bool(patch["enabled"])

        await self._save_settings(settings)
        return self._split_tunneling_from_core(settings)

    async def update_custom_dns(
        self, patch: dict[str, CustomDnsValue]
    ) -> CustomDnsSettings:
        settings = await self._load_settings()
        if self._user_tier() < 1:
            raise RuntimeError("Custom DNS requires a paid Proton VPN plan")

        final_enabled = patch.get("enabled", settings.custom_dns.enabled)
        if final_enabled and int(settings.features.netshield) != 0:
            raise ValueError("Disable NetShield before enabling custom DNS")

        if "servers" in patch:
            from proton.vpn.core.settings import CustomDNSEntry

            settings.custom_dns.ip_list = [
                CustomDNSEntry.new_from_string(
                    str(server["address"]),
                    enabled=bool(server["enabled"]),
                )
                for server in patch["servers"]
                if isinstance(server, dict)
            ]
        if "enabled" in patch:
            settings.custom_dns.enabled = bool(patch["enabled"])

        await self._save_settings(settings)
        return self._custom_dns_from_core(settings)

    async def _load_settings(self):
        try:
            return await self._api.load_settings()
        except Exception as error:
            if type(error).__name__ == "ProtonAPIAuthenticationNeeded":
                await self._raise_session_error(error)
            raise RuntimeError("Proton could not load the VPN settings") from None

    async def _save_settings(self, settings: Any) -> None:
        try:
            await self._api.save_settings(settings)
        except Exception as error:
            if type(error).__name__ == "ProtonAPIAuthenticationNeeded":
                await self._raise_session_error(error)
            raise RuntimeError("Proton could not save the VPN settings") from None

    async def connect_country(self, country_code: str) -> None:
        server_list = await self._get_server_list()
        await self._connect_logical(server_list.get_fastest_in_country(country_code))

    async def connect_server(self, server_name: str) -> None:
        server_list = await self._get_server_list()
        await self._connect_logical(server_list.get_by_name(server_name))

    async def _get_server_list(self):
        try:
            return await self._api.refresher.get_up_to_date_server_list()
        except Exception as error:
            await self._raise_session_error(error)

    def _normal_servers(self, server_list):
        from proton.vpn.session.servers import ServerFeatureEnum

        available = server_list.get_available_servers(
            server_list.logicals, server_list.user_tier
        )
        return server_list.get_servers_with_features(
            available,
            exclude_features=ServerFeatureEnum.SECURE_CORE | ServerFeatureEnum.TOR,
        )

    async def _connect_logical(self, logical_server) -> None:
        try:
            client_config = await self._api.refresher.get_up_to_date_client_config()
            vpn_server = self._connector.get_vpn_server(logical_server, client_config)
            settings = await self._api.load_settings()
            await self._connector.connect(vpn_server, protocol=settings.protocol)
        except Exception as error:
            await self._raise_session_error(error)

    def _settings_from_core(self, settings: Any) -> VpnSettings:
        disconnected = (
            type(self._connector.current_state).__name__.lower() == "disconnected"
        )
        return VpnSettings(
            protocol=settings.protocol,
            protocols=self._available_protocols(settings.protocol),
            kill_switch=int(settings.killswitch),
            net_shield=int(settings.features.netshield),
            vpn_accelerator=bool(settings.features.vpn_accelerator),
            moderate_nat=bool(settings.features.moderate_nat),
            port_forwarding=bool(settings.features.port_forwarding),
            ipv6=bool(settings.ipv6),
            anonymous_crash_reports=bool(settings.anonymous_crash_reports),
            paid_features_available=self._user_tier() >= 1,
            protocol_editable=disconnected,
            kill_switch_editable=disconnected,
            split_tunneling_enabled=bool(
                settings.features.split_tunneling.enabled
            ),
            custom_dns_enabled=bool(settings.custom_dns.enabled),
        )

    def _split_tunneling_from_core(
        self, settings: Any
    ) -> SplitTunnelingSettings:
        split_tunneling = settings.features.split_tunneling
        return SplitTunnelingSettings(
            available=bool(self._connector.is_split_tunneling_available),
            paid_features_available=self._user_tier() >= 1,
            enabled=bool(split_tunneling.enabled),
            mode=self._mode_value(split_tunneling.mode),
            exclude_app_paths=tuple(split_tunneling.exclude.app_paths),
            include_app_paths=tuple(split_tunneling.include.app_paths),
            exclude_ip_range_count=len(split_tunneling.exclude.ip_ranges),
            include_ip_range_count=len(split_tunneling.include.ip_ranges),
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
        groups = ["generic"]
        try:
            if self._api.refresher.feature_flags.get("ProTunV1"):
                groups.append("protun")
        except (AttributeError, TypeError):
            pass
        try:
            for group in groups:
                for candidate in self._connector.iter_available_protocols(group):
                    protocol_id = str(candidate.protocol)
                    if protocol_id in seen:
                        continue
                    seen.add(protocol_id)
                    protocols.append(
                        ProtocolInfo(protocol_id, str(candidate.ui_protocol))
                    )
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

    @staticmethod
    def _mode_value(mode: Any) -> str:
        return str(getattr(mode, "value", mode))

    async def disconnect(self) -> None:
        await self._connector.disconnect()

    async def login(self, username: str, password: str) -> None:
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
            raise RuntimeError("No two-factor authentication is pending")
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
            raise RuntimeError("No two-factor authentication is pending")
        if not bool(self._api.supports_fido2):
            raise RuntimeError("Security-key authentication is unavailable")

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
            raise RuntimeError("No security key is waiting for a PIN")
        self._set_auth_status("fido_waiting", "Waiting for the security key…")

    async def cancel_fido2(self) -> None:
        if self._fido_interaction:
            self._fido_interaction.cancel()

    async def logout(self) -> None:
        await self.cancel_fido2()
        if type(self._connector.current_state).__name__ != "Disconnected":
            await self._connector.disconnect()
        if self._reconnector:
            await self._reconnector.disable()
        self._session_services_enabled = False
        try:
            await self._api.logout()
        except Exception as error:
            if self._logged_in:
                await self._enable_session_services()
            error_name = type(error).__name__
            if error_name in {"ProtonAPINotReachable", "ProtonAPINotAvailable"}:
                raise RuntimeError(
                    "Proton's API is unreachable; sign-out was not completed"
                ) from None
            raise RuntimeError("Proton could not complete sign-out") from None
        await self._set_signed_out("Signed out")

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
        if self._api:
            self._api.refresher.set_server_list_updated_callback(None)
            self._api.refresher.set_server_loads_updated_callback(None)
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
        if self._server_data_callback:
            self._server_data_callback(True)

    def _on_server_loads_updated(self) -> None:
        if self._server_data_callback:
            self._server_data_callback(False)

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
        raise RuntimeError("Your Proton session expired; sign in again") from None

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

        connection = self._connector.current_connection if self._connector else None
        server_name = connection.server_name if connection else ""
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
            state=state_name,
            server_name=server_name,
            message=(
                self._status_message
                if self._logged_in
                else self._status_message or "Sign in to Proton VPN to continue"
            ),
        )
