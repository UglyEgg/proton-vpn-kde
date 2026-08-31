# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Provider-object translation and selection helpers for Proton servers."""

from __future__ import annotations

from typing import Any

from .controller import ServerInfo, normalize_server_features
from .errors import UserVisibleRuntimeError, UserVisibleValueError


def fastest_matching(server_list: Any, servers: Any, features: tuple[str, ...]):
    from proton.vpn.session.servers import ServerFeatureEnum

    normalized = normalize_server_features(features)
    feature_flags = {
        "p2p": ServerFeatureEnum.P2P,
        "streaming": ServerFeatureEnum.STREAMING,
        "tor": ServerFeatureEnum.TOR,
        "secure-core": ServerFeatureEnum.SECURE_CORE,
    }
    requested = ServerFeatureEnum(0)
    for feature in normalized:
        requested |= feature_flags[feature]
    available = server_list.get_available_servers(servers, server_list.user_tier)
    matching = server_list.get_servers_with_features(
        available,
        request_features=requested,
        exclude_features=ServerFeatureEnum(0),
    )
    logical_server = server_list.get_fastest_server(matching)
    if logical_server is None:
        raise UserVisibleRuntimeError("No server available in the current tier")
    return logical_server


def countries(server_list: Any):
    return server_list.group_by_country(
        group_by_location=True,
        include_free_servers=server_list.user_tier == 0,
    )


def country(server_list: Any, country_code: str):
    for candidate in countries(server_list):
        if candidate.code.upper() == country_code:
            return candidate
    raise UserVisibleValueError("The selected Proton country is no longer available")


def server_group(
    server_list: Any,
    country_code: str,
    group_kind: str,
    group_name: str,
):
    selected_country = country(server_list, country_code)
    if group_kind == "secure-core":
        group = selected_country.secure_core_group
        if group is not None and group.name == group_name:
            return group
    elif group_kind == "location":
        for location in selected_country.locations:
            if location.name == group_name:
                return location
    raise UserVisibleValueError(
        "The selected Proton server group is no longer available"
    )


def server_info(server_list: Any, server: Any) -> ServerInfo:
    from proton.vpn.session.servers import ServerFeatureEnum

    available = list(server_list.get_available_servers([server], server_list.user_tier))
    return ServerInfo(
        name=server.name,
        location=server.location or "",
        entry_country=server.entry_country.upper(),
        load=server.load or 0,
        accessible=bool(available),
        under_maintenance=server.under_maintenance,
        smart_routing=server.smart_routing,
        secure_core=ServerFeatureEnum.SECURE_CORE in server.features,
        tor=ServerFeatureEnum.TOR in server.features,
        p2p=ServerFeatureEnum.P2P in server.features,
        streaming=ServerFeatureEnum.STREAMING in server.features,
    )
