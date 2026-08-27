"""Desktop-neutral VPN state controller."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import asdict, dataclass, replace
import json
from typing import Callable, Protocol, TypeVar


@dataclass(frozen=True, slots=True)
class VpnSnapshot:
    """Non-sensitive state exposed to frontend processes."""

    schema_version: int = 1
    ready: bool = False
    logged_in: bool = False
    auth_state: str = "signed_out"
    account_name: str = ""
    plan_title: str = ""
    user_tier: int = 0
    max_connections: int = 0
    fido2_available: bool = False
    reconnect_enabled: bool = True
    busy: bool = False
    state: str = "starting"
    server_name: str = ""
    message: str = ""

    def to_json(self) -> str:
        payload = asdict(self)
        payload["schemaVersion"] = payload.pop("schema_version")
        payload["loggedIn"] = payload.pop("logged_in")
        payload["authState"] = payload.pop("auth_state")
        payload["accountName"] = payload.pop("account_name")
        payload["planTitle"] = payload.pop("plan_title")
        payload["userTier"] = payload.pop("user_tier")
        payload["maxConnections"] = payload.pop("max_connections")
        payload["fido2Available"] = payload.pop("fido2_available")
        payload["reconnectEnabled"] = payload.pop("reconnect_enabled")
        payload["serverName"] = payload.pop("server_name")
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True, slots=True)
class CountryInfo:
    code: str
    server_count: int


@dataclass(frozen=True, slots=True)
class ServerInfo:
    name: str
    location: str = ""
    load: int = 0
    p2p: bool = False
    streaming: bool = False


LocationInfo = TypeVar("LocationInfo", CountryInfo, ServerInfo)


def location_list_to_json(kind: str, items: list[LocationInfo]) -> str:
    payload_items = []
    for item in items:
        payload = asdict(item)
        if "server_count" in payload:
            payload["serverCount"] = payload.pop("server_count")
        payload_items.append(payload)
    return json.dumps(
        {"schemaVersion": 1, kind: payload_items},
        separators=(",", ":"),
        sort_keys=True,
    )


SnapshotCallback = Callable[[VpnSnapshot], None]


class CoreAdapter(Protocol):
    """Minimal surface required from Proton's networking core."""

    async def initialize(self, callback: SnapshotCallback) -> VpnSnapshot: ...
    async def get_countries(self) -> list[CountryInfo]: ...
    async def get_servers(self, country_code: str) -> list[ServerInfo]: ...
    async def connect_fastest(self) -> None: ...
    async def connect_country(self, country_code: str) -> None: ...
    async def connect_server(self, server_name: str) -> None: ...
    async def login(self, username: str, password: str) -> None: ...
    async def submit_two_factor(self, code: str) -> None: ...
    async def cancel_login(self) -> None: ...
    async def begin_fido2(self) -> None: ...
    async def submit_fido2_pin(self, pin: str) -> None: ...
    async def cancel_fido2(self) -> None: ...
    async def logout(self) -> None: ...
    async def set_reconnection_enabled(self, enabled: bool) -> None: ...
    async def disconnect(self) -> None: ...
    async def close(self) -> None: ...


class BackendController:
    """Serializes mutating operations and publishes immutable snapshots."""

    def __init__(self, adapter: CoreAdapter):
        self._adapter = adapter
        self._snapshot = VpnSnapshot()
        self._listeners: list[SnapshotCallback] = []
        self._operation_lock = asyncio.Lock()

    @property
    def snapshot(self) -> VpnSnapshot:
        return self._snapshot

    def subscribe(self, callback: SnapshotCallback) -> None:
        self._listeners.append(callback)

    async def start(self) -> None:
        try:
            snapshot = await self._adapter.initialize(self._on_adapter_snapshot)
        except Exception as error:  # Keep D-Bus available to report startup errors.
            self._publish(
                replace(
                    self._snapshot,
                    ready=False,
                    state="error",
                    message=f"Backend initialization failed: {error}",
                )
            )
        else:
            self._publish(snapshot)

    async def connect_fastest(self) -> None:
        if not self._snapshot.logged_in:
            raise RuntimeError("A Proton account session is required")
        await self._run_operation(self._adapter.connect_fastest)

    async def get_countries_json(self) -> str:
        self._require_session()
        return location_list_to_json("countries", await self._adapter.get_countries())

    async def get_servers_json(self, country_code: str) -> str:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        return location_list_to_json(
            "servers", await self._adapter.get_servers(normalized_code)
        )

    async def connect_country(self, country_code: str) -> None:
        self._require_session()
        normalized_code = self._validate_country_code(country_code)
        await self._run_operation(
            lambda: self._adapter.connect_country(normalized_code)
        )

    async def connect_server(self, server_name: str) -> None:
        self._require_session()
        normalized_name = server_name.strip()
        if not normalized_name or len(normalized_name) > 128:
            raise ValueError("Invalid Proton server name")
        await self._run_operation(lambda: self._adapter.connect_server(normalized_name))

    async def login(self, username: str, password: str) -> None:
        normalized_username = username.strip()
        if not normalized_username or len(normalized_username) > 320:
            raise ValueError("Enter a valid Proton username")
        if not password or len(password) > 4096:
            raise ValueError("Enter a valid Proton password")
        await self._run_operation(
            lambda: self._adapter.login(normalized_username, password)
        )

    async def submit_two_factor(self, code: str) -> None:
        normalized_code = code.strip()
        if len(normalized_code) not in {6, 8} or not normalized_code.isascii():
            raise ValueError("Enter a 6-digit code or an 8-character recovery code")
        await self._run_operation(
            lambda: self._adapter.submit_two_factor(normalized_code)
        )

    async def cancel_login(self) -> None:
        await self._run_operation(self._adapter.cancel_login)

    async def begin_fido2(self) -> None:
        await self._run_operation(self._adapter.begin_fido2)

    async def submit_fido2_pin(self, pin: str) -> None:
        if not pin or len(pin) > 256:
            raise ValueError("Enter the security-key PIN")
        await self._adapter.submit_fido2_pin(pin)

    async def cancel_fido2(self) -> None:
        await self._adapter.cancel_fido2()

    async def logout(self) -> None:
        await self._run_operation(self._adapter.logout)

    async def disconnect(self) -> None:
        await self._run_operation(self._adapter.disconnect)

    async def set_reconnection_enabled(self, enabled: bool) -> None:
        await self._adapter.set_reconnection_enabled(enabled)

    async def close(self) -> None:
        await self._adapter.close()

    def _require_session(self) -> None:
        if not self._snapshot.ready:
            raise RuntimeError("The Proton backend is not ready")
        if not self._snapshot.logged_in:
            raise RuntimeError("A Proton account session is required")

    @staticmethod
    def _validate_country_code(country_code: str) -> str:
        normalized_code = country_code.strip().upper()
        if (
            len(normalized_code) != 2
            or not normalized_code.isascii()
            or not normalized_code.isalpha()
        ):
            raise ValueError("Invalid country code")
        return normalized_code

    async def _run_operation(self, operation: Callable[[], Awaitable[None]]) -> None:
        if self._operation_lock.locked():
            raise RuntimeError("Another VPN operation is already in progress")

        async with self._operation_lock:
            self._publish(replace(self._snapshot, busy=True, message=""))
            try:
                await operation()
            except Exception as error:
                self._publish(
                    replace(
                        self._snapshot,
                        busy=False,
                        message=str(error),
                    )
                )
                raise
            else:
                self._publish(replace(self._snapshot, busy=False))

    def _on_adapter_snapshot(self, snapshot: VpnSnapshot) -> None:
        self._publish(replace(snapshot, busy=self._snapshot.busy))

    def _publish(self, snapshot: VpnSnapshot) -> None:
        if snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        for listener in tuple(self._listeners):
            listener(snapshot)
