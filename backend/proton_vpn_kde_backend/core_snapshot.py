# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Translate live Proton Core state into the stable frontend snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .controller import VpnSnapshot


@dataclass(frozen=True, slots=True)
class SnapshotContext:
    connector: Any
    api: Any
    startup_compatible: bool
    logged_in: bool
    auth_state: str
    reconnection_enabled: bool
    kill_switch: int
    packet_capture_active: bool
    core_memory_optimized: bool
    core_version: str
    status_message: str


def state_name(state: Any) -> str:
    candidate = type(state).__name__.lower() if state else "unavailable"
    if candidate in {
        "connected",
        "connecting",
        "disconnecting",
        "disconnected",
        "error",
    }:
        return candidate
    return "error"


def snapshot_from_state(state: Any, context: SnapshotContext) -> VpnSnapshot:
    current_state = state_name(state)
    error_code = _error_code(state) if current_state == "error" else ""
    connection = context.connector.current_connection if context.connector else None
    server_name = connection.server_name if connection else ""
    logical_server = _logical_server(context, server_name)
    forwarded_port = _forwarded_port(state) if current_state == "connected" else 0
    server = _server_metadata(logical_server)
    account = _account_metadata(context)

    return VpnSnapshot(
        ready=True,
        startup_compatible=context.startup_compatible,
        logged_in=context.logged_in,
        auth_state=context.auth_state,
        account_name=account[0],
        plan_title=account[1],
        user_tier=account[2],
        max_connections=account[3],
        fido2_available=(
            not context.logged_in
            and context.auth_state
            in {
                "two_factor",
                "fido_waiting",
                "fido_touch",
                "fido_select",
                "fido_pin",
                "fido_error",
            }
            and bool(context.api.supports_fido2)
        ),
        reconnect_enabled=context.reconnection_enabled,
        kill_switch=context.kill_switch,
        state=current_state,
        error_code=error_code,
        server_name=server_name,
        server_location=server[0],
        exit_country=server[1],
        entry_country=server[2],
        forwarded_port=forwarded_port,
        secure_core=server[3],
        tor=server[4],
        p2p=server[5],
        streaming=server[6],
        smart_routing=server[7],
        packet_capture_active=context.packet_capture_active,
        core_memory_optimized=context.core_memory_optimized,
        core_version=context.core_version,
        message=(
            context.status_message
            if context.logged_in
            else context.status_message or "Sign in to Proton VPN to continue"
        ),
    )


def _error_code(state: Any) -> str:
    event = getattr(getattr(state, "context", None), "event", None)
    return {
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


def _logical_server(context: SnapshotContext, server_name: str):
    if not server_name or not context.logged_in:
        return None
    try:
        return context.api.refresher.server_list.get_by_name(server_name)
    except Exception:
        return None


def _forwarded_port(state: Any) -> int:
    try:
        candidate = state.forwarded_port
    except Exception:
        return 0
    return candidate if type(candidate) is int and 0 < candidate <= 65535 else 0


def _server_metadata(logical_server: Any) -> tuple[str, str, str, bool, bool, bool, bool, bool]:
    if logical_server is None:
        return "", "", "", False, False, False, False, False

    from proton.vpn.session.servers import ServerFeatureEnum

    return (
        logical_server.location or "",
        logical_server.exit_country.upper(),
        logical_server.entry_country.upper(),
        ServerFeatureEnum.SECURE_CORE in logical_server.features,
        ServerFeatureEnum.TOR in logical_server.features,
        ServerFeatureEnum.P2P in logical_server.features,
        ServerFeatureEnum.STREAMING in logical_server.features,
        logical_server.smart_routing,
    )


def _account_metadata(context: SnapshotContext) -> tuple[str, str, int, int]:
    if not context.logged_in:
        return "", "", 0, 0
    account = context.api.account_data
    return (
        context.api.account_name or "",
        account.plan_title or "Free",
        account.max_tier,
        account.max_connections,
    )
