# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Version-one session D-Bus interface."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import inspect
import logging
from typing import Any, TYPE_CHECKING, TypeAlias, TypeVar

from dbus_fast.errors import DBusError
from dbus_fast.service import ServiceInterface, method, signal

from .controller import (
    BackendController,
    CustomDnsSettings,
    SplitTunnelingSettings,
    VpnSettings,
    VpnSnapshot,
)
from .client_authorization import (
    CLASSIFIED_METHODS,
    ClientAuthorizer,
    UNAUTHORIZED_ERROR,
    UNAUTHORIZED_MESSAGE,
    current_request_sender,
)
from .errors import UserVisibleError, UserVisibleRuntimeError
from .features import SUPPORT_REPORT_SUBMISSION_ENABLED
from .secret_payload import SecretPayloadReader, close_descriptor
from .lifetime import BackendLifetime


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # dbus-fast intentionally uses D-Bus signatures as string annotations.
    # These aliases let static analysis understand the scalar signatures
    # without changing the runtime annotations inspected by dbus-fast.
    s: TypeAlias = str
    h: TypeAlias = int
    b: TypeAlias = bool

BUS_NAME = "quest.entropy.PlasmaVPN.Backend"
OBJECT_PATH = "/quest/entropy/PlasmaVPN/Backend"
INTERFACE_NAME = "quest.entropy.PlasmaVPN.Backend1"
INVALID_SECRET_ERROR = "quest.entropy.PlasmaVPN.Error.InvalidSecretPayload"
INVALID_SETTINGS_ERROR = "quest.entropy.PlasmaVPN.Error.InvalidSettings"
INVALID_SPLIT_TUNNELING_ERROR = "quest.entropy.PlasmaVPN.Error.InvalidSplitTunneling"
INVALID_CUSTOM_DNS_ERROR = "quest.entropy.PlasmaVPN.Error.InvalidCustomDns"
INVALID_SUPPORT_REPORT_ERROR = "quest.entropy.PlasmaVPN.Error.InvalidSupportReport"
OPERATION_FAILED_ERROR = "quest.entropy.PlasmaVPN.Error.OperationFailed"
OPERATION_FAILED_MESSAGE = "The VPN operation could not be completed"
SUPPORT_REPORT_DISABLED_MESSAGE = (
    "Direct Proton support submission is disabled in this unofficial community build"
)
SECRET_OPERATIONS = frozenset(
    {
        "Login",
        "SubmitTwoFactor",
        "SubmitFido2Pin",
        "SubmitNpsSurvey",
        "SubmitSupportReport",
    }
)


Result = TypeVar("Result")


def _bounded_user_message(error: UserVisibleError, fallback: str) -> str:
    message = str(error).strip()
    if not message or len(message) > 256 or not message.isprintable():
        return fallback
    return message


def dbus_error_boundary(
    error_name: str = OPERATION_FAILED_ERROR,
    fallback_message: str = OPERATION_FAILED_MESSAGE,
):
    """Map an exported method failure to a stable, non-sensitive D-Bus error."""

    def decorate(operation: Callable[..., Result]):
        if inspect.iscoroutinefunction(operation):

            @wraps(operation)
            async def call_async(*args: Any, **kwargs: Any):
                try:
                    return await operation(*args, **kwargs)
                except DBusError:
                    raise
                except PermissionError:
                    raise DBusError(
                        UNAUTHORIZED_ERROR,
                        UNAUTHORIZED_MESSAGE,
                    ) from None
                except UserVisibleError as error:
                    raise DBusError(
                        error_name,
                        _bounded_user_message(error, fallback_message),
                    ) from None
                except Exception as error:
                    logger.error(
                        "D-Bus method %s failed (%s)",
                        operation.__name__,
                        type(error).__name__,
                    )
                    raise DBusError(error_name, fallback_message) from None

            call_async.__dbus_error_boundary__ = True  # type: ignore[attr-defined]
            return call_async

        @wraps(operation)
        def call_sync(*args: Any, **kwargs: Any):
            try:
                return operation(*args, **kwargs)
            except DBusError:
                raise
            except PermissionError:
                raise DBusError(
                    UNAUTHORIZED_ERROR,
                    UNAUTHORIZED_MESSAGE,
                ) from None
            except UserVisibleError as error:
                raise DBusError(
                    error_name,
                    _bounded_user_message(error, fallback_message),
                ) from None
            except Exception as error:
                logger.error(
                    "D-Bus method %s failed (%s)",
                    operation.__name__,
                    type(error).__name__,
                )
                raise DBusError(error_name, fallback_message) from None

        call_sync.__dbus_error_boundary__ = True  # type: ignore[attr-defined]
        return call_sync

    return decorate


class VpnDbusService(ServiceInterface):
    def __init__(
        self,
        controller: BackendController,
        lifetime: BackendLifetime | None = None,
        authorizer: ClientAuthorizer | None = None,
    ):
        super().__init__(INTERFACE_NAME)
        self._controller = controller
        self._lifetime = lifetime
        self._authorizer = authorizer
        self._secret_payloads = SecretPayloadReader()
        if authorizer is not None:
            authorizer.subscribe_revocation(self._secret_payloads.revoke_sender)
        controller.subscribe(self._on_snapshot)
        controller.subscribe_server_data(self._on_server_data)
        controller.subscribe_settings(self._on_settings)
        controller.subscribe_split_tunneling(self._on_split_tunneling)
        controller.subscribe_custom_dns(self._on_custom_dns)

    @method(name="AuthorizeClient")
    @dbus_error_boundary()
    async def authorize_client(self, unique_name: "s"):  # noqa: F722,F821
        if self._authorizer is not None:
            await self._authorizer.authorize(unique_name)

    @method(name="RegisterClient")
    @dbus_error_boundary()
    async def register_client(self, unique_name: "s"):  # noqa: F722,F821
        if self._authorizer is not None:
            await self._authorizer.authorize(unique_name)
            unique_name = current_request_sender()
        if self._lifetime is not None:
            await self._lifetime.register_client(unique_name)

    @method(name="UnregisterClient")
    @dbus_error_boundary()
    def unregister_client(self, unique_name: "s"):  # noqa: F722,F821
        if self._authorizer is not None:
            sender = self._authorizer.require_authorized_sender()
            if unique_name != sender:
                raise PermissionError(UNAUTHORIZED_MESSAGE)
            unique_name = sender
        if self._lifetime is not None:
            self._lifetime.unregister_client(unique_name)

    @method(name="GetSnapshot")
    @dbus_error_boundary()
    def get_snapshot(self) -> "s":  # noqa: F722,F821
        return self._controller.snapshot.to_json()

    @method(name="GetAuthPublicKey")
    @dbus_error_boundary()
    def get_auth_public_key(self, operation: "s") -> "s":  # noqa: F722,F821
        if operation not in SECRET_OPERATIONS:
            raise UserVisibleRuntimeError("The protected operation is unsupported")
        return self._secret_payloads.issue_public_key(
            current_request_sender(), operation
        )

    @method(name="ConnectFastest")
    @dbus_error_boundary()
    async def connect_fastest(self):
        await self._controller.connect_fastest()

    @method(name="ConnectFastestWithFeature")
    @dbus_error_boundary()
    async def connect_fastest_with_feature(self, feature: "s"):  # noqa: F722,F821
        await self._controller.connect_fastest_with_feature(feature)

    @method(name="ConnectFastestWithFeatures")
    @dbus_error_boundary()
    async def connect_fastest_with_features(self, features: "as"):  # type: ignore[valid-type]  # noqa: F722,F821
        await self._controller.connect_fastest_with_features(features)

    @method(name="GetCountries")
    @dbus_error_boundary()
    async def get_countries(self) -> "s":  # noqa: F722,F821
        return await self._controller.get_countries_json()

    @method(name="GetServerGroups")
    @dbus_error_boundary()
    async def get_server_groups(self, country_code: "s") -> "s":  # noqa: F722,F821
        return await self._controller.get_server_groups_json(country_code)

    @method(name="GetGroupServers")
    @dbus_error_boundary()
    async def get_group_servers(
        self,
        country_code: "s",  # noqa: F821
        group_kind: "s",  # noqa: F821
        group_name: "s",  # noqa: F722,F821
    ) -> "s":  # noqa: F722,F821
        return await self._controller.get_group_servers_json(
            country_code, group_kind, group_name
        )

    @method(name="GetServerLoads")
    @dbus_error_boundary()
    async def get_server_loads(self, country_code: "s") -> "s":  # noqa: F722,F821
        return await self._controller.get_server_loads_json(country_code)

    @method(name="SearchLocations")
    @dbus_error_boundary()
    async def search_locations(self, query: "s") -> "s":  # noqa: F722,F821
        return await self._controller.search_locations_json(query)

    @method(name="GetPendingNpsSurvey")
    @dbus_error_boundary()
    async def get_pending_nps_survey(self) -> "s":  # noqa: F722,F821
        return await self._controller.get_pending_nps_survey_json()

    @method(name="GetSettings")
    @dbus_error_boundary(
        INVALID_SETTINGS_ERROR,
        "The VPN settings could not be loaded",
    )
    async def get_settings(self) -> "s":  # noqa: F722,F821
        return await self._controller.get_settings_json()

    @method(name="UpdateSettings")
    @dbus_error_boundary(
        INVALID_SETTINGS_ERROR,
        "The VPN setting could not be changed",
    )
    async def update_settings(self, patch_json: "s") -> "s":  # noqa: F722,F821
        return await self._controller.update_settings_json(patch_json)

    @method(name="GetSplitTunneling")
    @dbus_error_boundary(
        INVALID_SPLIT_TUNNELING_ERROR,
        "The split-tunneling settings could not be loaded",
    )
    async def get_split_tunneling(self) -> "s":  # noqa: F722,F821
        return await self._controller.get_split_tunneling_json()

    @method(name="UpdateSplitTunneling")
    @dbus_error_boundary(
        INVALID_SPLIT_TUNNELING_ERROR,
        "The split-tunneling setting could not be changed",
    )
    async def update_split_tunneling(self, patch_json: "s") -> "s":  # noqa: F722,F821
        return await self._controller.update_split_tunneling_json(patch_json)

    @method(name="GetCustomDns")
    @dbus_error_boundary(
        INVALID_CUSTOM_DNS_ERROR,
        "The custom-DNS settings could not be loaded",
    )
    async def get_custom_dns(self) -> "s":  # noqa: F722,F821
        return await self._controller.get_custom_dns_json()

    @method(name="UpdateCustomDns")
    @dbus_error_boundary(
        INVALID_CUSTOM_DNS_ERROR,
        "The custom-DNS setting could not be changed",
    )
    async def update_custom_dns(self, patch_json: "s") -> "s":  # noqa: F722,F821
        return await self._controller.update_custom_dns_json(patch_json)

    @method(name="ConnectCountry")
    @dbus_error_boundary()
    async def connect_country(self, country_code: "s"):  # noqa: F722,F821
        await self._controller.connect_country(country_code)

    @method(name="ConnectCountryWithFeatures")
    @dbus_error_boundary()
    async def connect_country_with_features(
        self,
        country_code: "s",  # noqa: F821
        features: "as",  # type: ignore[valid-type]  # noqa: F722,F821
    ):
        await self._controller.connect_country_with_features(country_code, features)

    @method(name="ConnectGroup")
    @dbus_error_boundary()
    async def connect_group(
        self,
        country_code: "s",  # noqa: F821
        group_kind: "s",  # noqa: F821
        group_name: "s",  # noqa: F722,F821
    ):
        await self._controller.connect_group(country_code, group_kind, group_name)

    @method(name="ConnectGroupWithFeatures")
    @dbus_error_boundary()
    async def connect_group_with_features(
        self,
        country_code: "s",  # noqa: F821
        group_kind: "s",  # noqa: F821
        group_name: "s",  # noqa: F821
        features: "as",  # type: ignore[valid-type]  # noqa: F722,F821
    ):
        await self._controller.connect_group_with_features(
            country_code, group_kind, group_name, features
        )

    @method(name="ConnectServer")
    @dbus_error_boundary()
    async def connect_server(self, server_name: "s"):  # noqa: F722,F821
        await self._controller.connect_server(server_name)

    @method(name="Disconnect")
    @dbus_error_boundary()
    async def disconnect(self):
        await self._controller.disconnect()

    @method(name="StartPacketCapture")
    @dbus_error_boundary()
    async def start_packet_capture(self, directory_path: "s"):  # noqa: F722,F821
        await self._controller.start_packet_capture(directory_path)

    @method(name="StopPacketCapture")
    @dbus_error_boundary()
    async def stop_packet_capture(self):
        await self._controller.stop_packet_capture()

    @method(name="SubmitSupportReport")
    @dbus_error_boundary(
        INVALID_SUPPORT_REPORT_ERROR,
        "The issue report could not be submitted",
    )
    async def submit_support_report(self, secret_fd: "h"):  # noqa: F722,F821
        if not SUPPORT_REPORT_SUBMISSION_ENABLED:
            close_descriptor(secret_fd)
            raise UserVisibleRuntimeError(SUPPORT_REPORT_DISABLED_MESSAGE)
        payload = self._read_secret(
            secret_fd,
            "SubmitSupportReport",
            {"username", "email", "description", "includeLogs"},
        )
        await self._controller.submit_support_report(
            payload["username"],
            payload["email"],
            payload["description"],
            payload["includeLogs"],
        )

    @method(name="SubmitNpsSurvey")
    @dbus_error_boundary()
    async def submit_nps_survey(self, secret_fd: "h"):  # noqa: F722,F821
        payload = self._read_secret(
            secret_fd,
            "SubmitNpsSurvey",
            {"score", "comments", "responseType"},
        )
        await self._controller.submit_nps_survey(
            payload["score"], payload["comments"], payload["responseType"]
        )

    @method(name="Login")
    @dbus_error_boundary()
    async def login(self, secret_fd: "h"):  # noqa: F722,F821
        payload = self._read_secret(secret_fd, "Login", {"username", "password"})
        await self._controller.login(payload["username"], payload["password"])

    @method(name="SubmitTwoFactor")
    @dbus_error_boundary()
    async def submit_two_factor(self, secret_fd: "h"):  # noqa: F722,F821
        payload = self._read_secret(secret_fd, "SubmitTwoFactor", {"code"})
        await self._controller.submit_two_factor(payload["code"])

    @method(name="CancelLogin")
    @dbus_error_boundary()
    async def cancel_login(self):
        await self._controller.cancel_login()

    @method(name="BeginFido2")
    @dbus_error_boundary()
    async def begin_fido2(self):
        await self._controller.begin_fido2()

    @method(name="SubmitFido2Pin")
    @dbus_error_boundary()
    async def submit_fido2_pin(self, secret_fd: "h"):  # noqa: F722,F821
        payload = self._read_secret(secret_fd, "SubmitFido2Pin", {"pin"})
        await self._controller.submit_fido2_pin(payload["pin"])

    @method(name="CancelFido2")
    @dbus_error_boundary()
    async def cancel_fido2(self):
        await self._controller.cancel_fido2()

    @method(name="Logout")
    @dbus_error_boundary()
    async def logout(self):
        await self._controller.logout()

    @method(name="DisableKillSwitchForLogin")
    @dbus_error_boundary(
        INVALID_SETTINGS_ERROR,
        "The kill switch could not be disabled",
    )
    async def disable_kill_switch_for_login(self):
        await self._controller.disable_kill_switch_for_login()

    @method(name="SetReconnectionEnabled")
    @dbus_error_boundary()
    async def set_reconnection_enabled(self, enabled: "b"):  # noqa: F722,F821
        await self._controller.set_reconnection_enabled(enabled)

    @signal(name="SnapshotChanged")
    def snapshot_changed(self, snapshot_json: "s") -> "s":  # noqa: F722,F821
        return snapshot_json

    @signal(name="ServerDataChanged")
    def server_data_changed(self, topology_changed: "b") -> "b":  # noqa: F722,F821
        return topology_changed

    @signal(name="SettingsChanged")
    def settings_changed(self, settings_json: "s") -> "s":  # noqa: F722,F821
        return settings_json

    @signal(name="SplitTunnelingChanged")
    def split_tunneling_changed(self, settings_json: "s") -> "s":  # noqa: F722,F821
        return settings_json

    @signal(name="CustomDnsChanged")
    def custom_dns_changed(self, settings_json: "s") -> "s":  # noqa: F722,F821
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
        operation: str,
        required_fields: set[str],
    ) -> dict[str, str]:
        try:
            return self._secret_payloads.read(
                current_request_sender(), operation, secret_fd, required_fields
            )
        except ValueError as error:
            raise DBusError(
                INVALID_SECRET_ERROR,
                "Protected authentication data was rejected; try again",
            ) from error


def exported_method_names() -> frozenset[str]:
    """Expose the declared method set for the authorization meta-test."""
    return frozenset(
        member.__DBUS_METHOD.name
        for member in vars(VpnDbusService).values()
        if getattr(member, "__DBUS_METHOD", None) is not None
    )


assert exported_method_names() == CLASSIFIED_METHODS
