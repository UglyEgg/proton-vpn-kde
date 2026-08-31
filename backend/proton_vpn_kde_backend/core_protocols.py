# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Protocol discovery over Proton Core's public connector contract."""

from __future__ import annotations

from typing import Any, Iterator

from .controller import ProtocolInfo


def iter_available_protocols(api: Any, connector: Any) -> Iterator[Any]:
    groups = ["generic"]
    try:
        if api.refresher.feature_flags.get("ProTunV1"):
            groups.append("protun")
    except (AttributeError, TypeError):
        pass
    for group in groups:
        yield from connector.iter_available_protocols(group)


def available_protocols(
    api: Any,
    connector: Any,
    current_protocol: str,
) -> tuple[ProtocolInfo, ...]:
    protocols: list[ProtocolInfo] = []
    seen: set[str] = set()
    try:
        for candidate in iter_available_protocols(api, connector):
            protocol_id = str(candidate.protocol)
            if protocol_id in seen:
                continue
            seen.add(protocol_id)
            protocols.append(ProtocolInfo(protocol_id, str(candidate.ui_protocol)))
    except (AttributeError, TypeError):
        pass
    if current_protocol not in seen:
        protocols.append(ProtocolInfo(current_protocol, current_protocol))
    return tuple(protocols)


def protocol_supports_packet_capture(
    api: Any,
    connector: Any,
    protocol: str,
) -> bool:
    try:
        for candidate in iter_available_protocols(api, connector):
            if str(candidate.protocol) == protocol and bool(
                candidate.supports_packet_capture()
            ):
                return True
    except (AttributeError, TypeError):
        pass
    return False
