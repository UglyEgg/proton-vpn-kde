"""Version-one session D-Bus interface."""

from __future__ import annotations

from dbus_fast.service import ServiceInterface, method, signal

from .controller import BackendController, VpnSnapshot


BUS_NAME = "proton.vpn.app.kde.backend"
OBJECT_PATH = "/proton/vpn/app/kde/backend"
INTERFACE_NAME = "proton.vpn.app.kde.Backend1"


class VpnDbusService(ServiceInterface):
    def __init__(self, controller: BackendController):
        super().__init__(INTERFACE_NAME)
        self._controller = controller
        controller.subscribe(self._on_snapshot)

    @method(name="GetSnapshot")
    def get_snapshot(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return self._controller.snapshot.to_json()

    @method(name="ConnectFastest")
    async def connect_fastest(self):
        await self._controller.connect_fastest()

    @method(name="GetCountries")
    async def get_countries(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_countries_json()

    @method(name="GetServers")
    async def get_servers(self, country_code: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_servers_json(country_code)

    @method(name="ConnectCountry")
    async def connect_country(self, country_code: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.connect_country(country_code)

    @method(name="ConnectServer")
    async def connect_server(self, server_name: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.connect_server(server_name)

    @method(name="Disconnect")
    async def disconnect(self):
        await self._controller.disconnect()

    @method(name="SetReconnectionEnabled")
    async def set_reconnection_enabled(self, enabled: "b"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.set_reconnection_enabled(enabled)

    @signal(name="SnapshotChanged")
    def snapshot_changed(self, snapshot_json: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return snapshot_json

    def _on_snapshot(self, snapshot: VpnSnapshot) -> None:
        self.snapshot_changed(snapshot.to_json())
