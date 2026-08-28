"""Version-one session D-Bus interface."""

from __future__ import annotations

from dbus_fast.errors import DBusError
from dbus_fast.service import ServiceInterface, method, signal

from .controller import (
    BackendController,
    CustomDnsSettings,
    SplitTunnelingSettings,
    VpnSettings,
    VpnSnapshot,
)
from .secret_payload import SecretPayloadReader
from .lifetime import BackendLifetime


BUS_NAME = "proton.vpn.app.kde.backend"
OBJECT_PATH = "/proton/vpn/app/kde/backend"
INTERFACE_NAME = "proton.vpn.app.kde.Backend1"
INVALID_SECRET_ERROR = "proton.vpn.app.kde.Error.InvalidSecretPayload"
INVALID_SETTINGS_ERROR = "proton.vpn.app.kde.Error.InvalidSettings"
INVALID_SPLIT_TUNNELING_ERROR = "proton.vpn.app.kde.Error.InvalidSplitTunneling"
INVALID_CUSTOM_DNS_ERROR = "proton.vpn.app.kde.Error.InvalidCustomDns"
INVALID_SUPPORT_REPORT_ERROR = "proton.vpn.app.kde.Error.InvalidSupportReport"


class VpnDbusService(ServiceInterface):
    def __init__(
        self, controller: BackendController, lifetime: BackendLifetime | None = None
    ):
        super().__init__(INTERFACE_NAME)
        self._controller = controller
        self._lifetime = lifetime
        self._secret_payloads = SecretPayloadReader()
        controller.subscribe(self._on_snapshot)
        controller.subscribe_server_data(self._on_server_data)
        controller.subscribe_settings(self._on_settings)
        controller.subscribe_split_tunneling(self._on_split_tunneling)
        controller.subscribe_custom_dns(self._on_custom_dns)

    @method(name="RegisterClient")
    async def register_client(self, unique_name: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        if self._lifetime is not None:
            await self._lifetime.register_client(unique_name)

    @method(name="UnregisterClient")
    def unregister_client(self, unique_name: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        if self._lifetime is not None:
            self._lifetime.unregister_client(unique_name)

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

    @method(name="GetServerGroups")
    async def get_server_groups(self, country_code: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_server_groups_json(country_code)

    @method(name="GetGroupServers")
    async def get_group_servers(
        self,
        country_code: "s",  # noqa: F821
        group_kind: "s",  # noqa: F821
        group_name: "s",  # type: ignore[valid-type]  # noqa: F722,F821
    ) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_group_servers_json(
            country_code, group_kind, group_name
        )

    @method(name="GetServerLoads")
    async def get_server_loads(self, country_code: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_server_loads_json(country_code)

    @method(name="SearchLocations")
    async def search_locations(self, query: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.search_locations_json(query)

    @method(name="GetPendingNpsSurvey")
    async def get_pending_nps_survey(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return await self._controller.get_pending_nps_survey_json()

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
            return await self._controller.update_split_tunneling_json(patch_json)
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_SPLIT_TUNNELING_ERROR, str(error)) from error

    @method(name="GetCustomDns")
    async def get_custom_dns(self) -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        try:
            return await self._controller.get_custom_dns_json()
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_CUSTOM_DNS_ERROR, str(error)) from error

    @method(name="UpdateCustomDns")
    async def update_custom_dns(self, patch_json: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        try:
            return await self._controller.update_custom_dns_json(patch_json)
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_CUSTOM_DNS_ERROR, str(error)) from error

    @method(name="ConnectCountry")
    async def connect_country(self, country_code: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.connect_country(country_code)

    @method(name="ConnectGroup")
    async def connect_group(
        self,
        country_code: "s",  # noqa: F821
        group_kind: "s",  # noqa: F821
        group_name: "s",  # type: ignore[valid-type]  # noqa: F722,F821
    ):
        await self._controller.connect_group(country_code, group_kind, group_name)

    @method(name="ConnectServer")
    async def connect_server(self, server_name: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.connect_server(server_name)

    @method(name="Disconnect")
    async def disconnect(self):
        await self._controller.disconnect()

    @method(name="StartPacketCapture")
    async def start_packet_capture(self, directory_path: "s"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.start_packet_capture(directory_path)

    @method(name="StopPacketCapture")
    async def stop_packet_capture(self):
        await self._controller.stop_packet_capture()

    @method(name="SubmitSupportReport")
    async def submit_support_report(self, secret_fd: "h"):  # type: ignore[valid-type]  # noqa: F722,F821
        payload = self._read_secret(
            secret_fd,
            {"username", "email", "description", "includeLogs"},
        )
        try:
            await self._controller.submit_support_report(
                payload["username"],
                payload["email"],
                payload["description"],
                payload["includeLogs"],
            )
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_SUPPORT_REPORT_ERROR, str(error)) from error

    @method(name="SubmitNpsSurvey")
    async def submit_nps_survey(self, secret_fd: "h"):  # type: ignore[valid-type]  # noqa: F722,F821
        payload = self._read_secret(
            secret_fd,
            {"score", "comments", "responseType"},
        )
        await self._controller.submit_nps_survey(
            payload["score"], payload["comments"], payload["responseType"]
        )

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

    @method(name="DisableKillSwitchForLogin")
    async def disable_kill_switch_for_login(self):
        try:
            await self._controller.disable_kill_switch_for_login()
        except (RuntimeError, ValueError) as error:
            raise DBusError(INVALID_SETTINGS_ERROR, str(error)) from error

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

    @signal(name="CustomDnsChanged")
    def custom_dns_changed(self, settings_json: "s") -> "s":  # type: ignore[valid-type]  # noqa: F722,F821
        return settings_json

    def _on_snapshot(self, snapshot: VpnSnapshot) -> None:
        self.snapshot_changed(snapshot.to_json())

    def _on_server_data(self, topology_changed: bool) -> None:
        self.server_data_changed(topology_changed)

    def _on_settings(self, settings: VpnSettings) -> None:
        self.settings_changed(settings.to_json())

    def _on_split_tunneling(self, settings: SplitTunnelingSettings) -> None:
        self.split_tunneling_changed(settings.to_json())

    def _on_custom_dns(self, settings: CustomDnsSettings) -> None:
        self.custom_dns_changed(settings.to_json())

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
