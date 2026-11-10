# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Provider-object translation and selection helpers for Proton servers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .controller import ServerInfo, normalize_server_features
from .errors import UserVisibleRuntimeError, UserVisibleValueError


def _matching_servers(
    server_list: Any, servers: Any, features: tuple[str, ...] | None,
):
    from proton.vpn.session.servers import ServerFeatureEnum

    normalized = normalize_server_features(features or ())
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
    return server_list.get_servers_with_features(
        available,
        request_features=requested,
        # Ordinary Core Fastest excludes these modes. An explicit feature
        # selection (including an empty intersection) has no such exclusion.
        exclude_features=(
            ServerFeatureEnum.SECURE_CORE | ServerFeatureEnum.TOR
            if features is None else ServerFeatureEnum(0)
        ),
    )


def fastest_matching(server_list: Any, servers: Any, features: tuple[str, ...]):
    matching = _matching_servers(server_list, servers, features)
    logical_server = server_list.get_fastest_server(matching)
    if logical_server is None:
        raise UserVisibleRuntimeError("No server available in the current tier")
    return logical_server


@dataclass(frozen=True, slots=True)
class FastestSelection:
    """Non-secret, process-local constraints from an explicit Fastest request.

    None features retain ordinary Core Fastest's mode exclusions; a tuple
    retains the exact feature intersection requested by the caller.
    """

    features: tuple[str, ...] | None = None
    country_code: str = ""
    group_kind: str = ""
    group_name: str = ""

    def pick(
        self, server_list: Any, preferred_id: str, excluded_ids: set[str],
        *, only_preferred: bool = False,
    ) -> Any:
        if preferred_id and preferred_id not in excluded_ids:
            from proton.vpn.session.exceptions import ServerNotFoundError

            try:
                preferred = server_list.get_by_id(preferred_id)
            except ServerNotFoundError:
                preferred = None
            if preferred is not None:
                try:
                    scoped = self._scoped_servers(server_list, [preferred])
                except UserVisibleValueError:
                    # This object is no longer in the selected group. Only
                    # the full selected pool can supply an alternative.
                    scoped = ()
                eligible = next(iter(_matching_servers(server_list, scoped, self.features)), None)
                if eligible is not None:
                    return eligible
        if only_preferred:
            return None
        servers = self._scoped_servers(server_list, server_list.logicals)
        matching = _matching_servers(server_list, servers, self.features)
        return server_list.get_fastest_server(
            server for server in matching if server.id not in excluded_ids
        )

    def _scoped_servers(self, server_list: Any, servers: Any) -> Any:
        if self.country_code:
            servers = server_list.get_servers_in_country_code(servers, self.country_code)
        if not self.group_kind:
            return servers
        from proton.vpn.session.servers import ServerList

        # Let Core retain location/free/Secure Core semantics, but build its
        # presentation groups only for this country (or one preferred object).
        # A fresh list prevents Core's in-place sorting from touching the cache.
        scoped = ServerList(
            user_tier=server_list.user_tier, logicals=list(servers), index_servers=False,
        )
        return server_group(
            scoped, self.country_code, self.group_kind, self.group_name
        ).servers


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
