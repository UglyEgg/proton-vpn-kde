# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Translate Proton Core settings objects into the stable backend contract."""

from __future__ import annotations

from typing import Any

from .controller import (
    CustomDnsServer,
    CustomDnsSettings,
    ProtocolInfo,
    SplitTunnelingSettings,
    VpnSettings,
)


def kill_switch_value(settings: Any) -> int:
    try:
        value = int(settings.killswitch)
    except (AttributeError, TypeError, ValueError):
        return 0
    return value if value in {0, 1, 2} else 0


def mode_value(mode: Any) -> str:
    return str(getattr(mode, "value", mode))


def protocol_supports_split_tunneling(protocol: str) -> bool:
    return protocol == "wireguard" or protocol.startswith("protun-")


def vpn_settings_from_core(
    settings: Any,
    *,
    protocols: tuple[ProtocolInfo, ...],
    user_tier: int,
    disconnected: bool,
    packet_capture_supported: bool,
) -> VpnSettings:
    return VpnSettings(
        protocol=settings.protocol,
        protocols=protocols,
        kill_switch=kill_switch_value(settings),
        net_shield=int(settings.features.netshield),
        vpn_accelerator=bool(settings.features.vpn_accelerator),
        moderate_nat=bool(settings.features.moderate_nat),
        port_forwarding=bool(settings.features.port_forwarding),
        ipv6=bool(settings.ipv6),
        anonymous_crash_reports=bool(settings.anonymous_crash_reports),
        paid_features_available=user_tier >= 1,
        protocol_editable=disconnected,
        kill_switch_editable=disconnected,
        split_tunneling_enabled=bool(settings.features.split_tunneling.enabled),
        custom_dns_enabled=bool(settings.custom_dns.enabled),
        packet_capture_supported=packet_capture_supported,
    )


def split_tunneling_from_core(
    settings: Any,
    *,
    available: bool,
    user_tier: int,
) -> SplitTunnelingSettings:
    split_tunneling = settings.features.split_tunneling
    return SplitTunnelingSettings(
        available=available,
        paid_features_available=user_tier >= 1,
        enabled=bool(split_tunneling.enabled),
        mode=mode_value(split_tunneling.mode),
        exclude_app_paths=tuple(split_tunneling.exclude.app_paths),
        include_app_paths=tuple(split_tunneling.include.app_paths),
        exclude_ip_ranges=tuple(
            str(ip_range) for ip_range in split_tunneling.exclude.ip_ranges
        ),
        include_ip_ranges=tuple(
            str(ip_range) for ip_range in split_tunneling.include.ip_ranges
        ),
    )


def custom_dns_from_core(settings: Any, *, user_tier: int) -> CustomDnsSettings:
    return CustomDnsSettings(
        paid_features_available=user_tier >= 1,
        enabled=bool(settings.custom_dns.enabled),
        servers=tuple(
            CustomDnsServer(
                address=entry.ip.compressed,
                enabled=bool(entry.enabled),
            )
            for entry in settings.custom_dns.ip_list
        ),
    )
