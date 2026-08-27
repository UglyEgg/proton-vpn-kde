"""Proton core and safe demo backend adapters."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

from .controller import CountryInfo, ServerInfo, SnapshotCallback, VpnSnapshot
from .reconnector import AsyncReconnector


class DemoCoreAdapter:
    """Deterministic adapter that never touches the network or credentials."""

    def __init__(self):
        self._callback: SnapshotCallback | None = None
        self._snapshot = VpnSnapshot(
            ready=True,
            logged_in=True,
            state="disconnected",
            message="Safe demo backend",
        )
        self._reconnection_enabled = True

    async def initialize(self, callback: SnapshotCallback) -> VpnSnapshot:
        self._callback = callback
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

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        self._reconnection_enabled = enabled
        self._snapshot = replace(self._snapshot, reconnect_enabled=enabled)
        if self._callback:
            self._callback(self._snapshot)

    async def close(self) -> None:
        return None

    async def _transition(self, state: str, server_name: str) -> None:
        self._snapshot = VpnSnapshot(
            ready=True,
            logged_in=True,
            reconnect_enabled=self._reconnection_enabled,
            state=state,
            server_name=server_name,
        )
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
        self._logged_in = False
        self._reconnector: AsyncReconnector | None = None
        self._reconnection_enabled = True
        self._status_message = ""

    async def initialize(self, callback: SnapshotCallback) -> VpnSnapshot:
        self._callback = callback
        if self._api is None:
            from proton.vpn.core.api import ProtonVPNAPI
            from proton.vpn.core.session_holder import ClientTypeMetadata

            self._api = ProtonVPNAPI(ClientTypeMetadata(type="gui"))

        # Proton SSO reaches Secret Service through a synchronous keyring API.
        # Warm the cached session away from the D-Bus asyncio thread so a
        # provider unlock prompt (KeePassXC, KWallet, etc.) cannot freeze the
        # entire backend while waiting for user approval.
        self._logged_in = await asyncio.to_thread(self._api.is_user_logged_in)
        self._connector = await self._api.get_vpn_connector()
        self._connector.register(self)

        if self._logged_in:
            await self._api.refresher.enable()
            self._reconnector = AsyncReconnector(
                self._connector,
                self._api.refresher,
                self._on_reconnector_status,
            )
            if self._reconnection_enabled:
                self._reconnector.enable()

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
            for server in sorted(servers, key=lambda item: (item.load, item.name))
        ]

    async def connect_country(self, country_code: str) -> None:
        server_list = await self._get_server_list()
        await self._connect_logical(server_list.get_fastest_in_country(country_code))

    async def connect_server(self, server_name: str) -> None:
        server_list = await self._get_server_list()
        await self._connect_logical(server_list.get_by_name(server_name))

    async def _get_server_list(self):
        return await self._api.refresher.get_up_to_date_server_list()

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
        client_config = await self._api.refresher.get_up_to_date_client_config()
        vpn_server = self._connector.get_vpn_server(logical_server, client_config)
        settings = await self._api.load_settings()
        await self._connector.connect(vpn_server, protocol=settings.protocol)

    async def disconnect(self) -> None:
        await self._connector.disconnect()

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        self._reconnection_enabled = enabled
        if not self._reconnector:
            return
        if enabled:
            self._reconnector.enable()
        else:
            await self._reconnector.disable()

    async def close(self) -> None:
        if self._reconnector:
            await self._reconnector.disable()
        if self._connector:
            self._connector.unregister(self)
        if self._api and self._logged_in:
            await self._api.refresher.disable()

    def status_update(self, state: Any) -> None:
        if self._callback:
            self._callback(self._snapshot_from_state(state))

    def _on_reconnector_status(self, message: str) -> None:
        self._status_message = message
        if self._callback and self._connector:
            self._callback(self._snapshot_from_state(self._connector.current_state))

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
        return VpnSnapshot(
            ready=True,
            logged_in=self._logged_in,
            reconnect_enabled=self._reconnection_enabled,
            state=state_name,
            server_name=server_name,
            message=(
                self._status_message
                if self._logged_in
                else "Sign in to Proton VPN to continue"
            ),
        )
