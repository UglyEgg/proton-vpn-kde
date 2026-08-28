"""Version-one session D-Bus interface."""

from __future__ import annotations

from dbus_fast.errors import DBusError
from dbus_fast.service import ServiceInterface, method, signal

from .controller import (
    BackendController,
    SplitTunnelingSettings,
    VpnSettings,
    VpnSnapshot,
)
from .secret_payload import SecretPayloadReader


BUS_NAME = "proton.vpn.app.kde.backend"
OBJECT_PATH = "/proton/vpn/app/kde/backend"
INTERFACE_NAME = "proton.vpn.app.kde.Backend1"
INVALID_SECRET_ERROR = "proton.vpn.app.kde.Error.InvalidSecretPayload"
INVALID_SETTINGS_ERROR = "proton.vpn.app.kde.Error.InvalidSettings"
INVALID_SPLIT_TUNNELING_ERROR = (
    "proton.vpn.app.kde.Error.InvalidSplitTunneling"
)


class VpnDbusService(ServiceInterface):
    def __init__(self, controller: BackendController):
        super().__init__(INTERFACE_NAME)
        self._controller = controller
        self._secret_payloads = SecretPayloadReader()
        controller.subscribe(self._on_snapshot)
        controller.subscribe_server_data(self._on_server_data)
        controller.subscribe_settings(self._on_settings)
        controller.subscribe_split_tunneling(self._on_split_tunneling)

    @method(name="GetSnapshot")
    def get_snapshot(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return self._controller.snapshot.to_json()

    @method(name="GetAuthPublicKey")
    def get_auth_public_key(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return self._secret_payloads.public_key

    @method(name="ConnectFastest")
    async def connect_fastest(self):
        await self._controller.connect_fastest()

    @method(name="GetCountries")
    async def get_countries(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_countries_json()

    @method(name="GetServers")
    async def get_servers(self, country_code: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_servers_json(country_code)

    @method(name="GetServerLoads")
    async def get_server_loads(self, country_code: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_server_loads_json(country_code)

    @method(name="GetSettings")
    async def get_settings(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        try:
            return await self._controller.get_settings_json()
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_SETTINGS_ERROR, str(error)) from error

    @method(name="UpdateSettings")
    async def update_settings(self, patch_json: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        try:
            return await self._controller.update_settings_json(patch_json)
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_SETTINGS_ERROR, str(error)) from error

    @method(name="GetSplitTunneling")
    async def get_split_tunneling(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        try:
            return await self._controller.get_split_tunneling_json()
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_SPLIT_TUNNELING_ERROR, str(error)) from error

    @method(name="UpdateSplitTunneling")
    async def update_split_tunneling(self, patch_json: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        try:
            return await self._controller.update_split_tunneling_json(
                patch_json
            )
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_SPLIT_TUNNELING_ERROR, str(error)) from error

    @method(name="ConnectCountry")
    async def connect_country(self, country_code: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.connect_country(country_code)

    @method(name="ConnectServer")
    async def connect_server(self, server_name: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.connect_server(server_name)

    @method(name="Disconnect")
    async def disconnect(self):
        await self._controller.disconnect()

    @method(name="Login")
    async def login(self, secret_fd: "h"):  # type: ignore[valid-type]  # noqa: F722,F821
        payload = self._read_secret(secret_fd, {"username", "password"})
        await self._controller.login(payload["username"], payload["password"])

    @method(name="SubmitTwoFactor")
    async def submit_two_factor(self, secret_fd: "h"):  # type: ignore[valid-type]  # noqa: F722,F821
        payload = self._read_secret(secret_fd, {"code"})
        await self._controller.submit_two_factor(payload["code"])

    @method(name="CancelLogin")
    async def cancel_login(self):
        await self._controller.cancel_login()

    @method(name="BeginFido2")
    async def begin_fido2(self):
        await self._controller.begin_fido2()

    @method(name="SubmitFido2Pin")
    async def submit_fido2_pin(self, secret_fd: "h"):  # type: ignore[valid-type]  # noqa: F722,F821
        payload = self._read_secret(secret_fd, {"pin"})
        await self._controller.submit_fido2_pin(payload["pin"])

    @method(name="CancelFido2")
    async def cancel_fido2(self):
        await self._controller.cancel_fido2()

    @method(name="Logout")
    async def logout(self):
        await self._controller.logout()

    @method(name="SetReconnectionEnabled")
    async def set_reconnection_enabled(self, enabled: "b"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.set_reconnection_enabled(enabled)

    @signal(name="SnapshotChanged")
    def snapshot_changed(self, snapshot_json: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return snapshot_json

    @signal(name="ServerDataChanged")
    def server_data_changed(self, topology_changed: "b") -> "b":  # type: ignore[valid-type]  # noqa: F722,F821
        return topology_changed

    @signal(name="SettingsChanged")
    def settings_changed(self, settings_json: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return settings_json

    @signal(name="SplitTunnelingChanged")
    def split_tunneling_changed(self, settings_json: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return settings_json

    def _on_snapshot(self, snapshot: VpnSnapshot) -> None:
        self.snapshot_changed(snapshot.to_json())

    def _on_server_data(self, topology_changed: bool) -> None:
        self.server_data_changed(topology_changed)

    def _on_settings(self, settings: VpnSettings) -> None:
        self.settings_changed(settings.to_json())

    def _on_split_tunneling(
        self, settings: SplitTunnelingSettings
    ) -> None:
        self.split_tunneling_changed(settings.to_json())

    def _read_secret(
        self,
        secret_fd: int,
        required_fields: set[str],
    ) -> dict[str, str]:
        try:
            return self._secret_payloads.read(secret_fd, required_fields)
        except ValueError as error:
            raise DBusError(
                INVALID_SECRET_ERROR,
                "Protected authentication data was rejected; try again",
            ) from error
