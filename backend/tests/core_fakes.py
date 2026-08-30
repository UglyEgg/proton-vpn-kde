# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Hermetic public-Core objects used by isolated adapter tests."""

from __future__ import annotations

from enum import Enum, IntFlag
from ipaddress import ip_address
from types import ModuleType
from typing import Any


class ServerFeatureEnum(IntFlag):
    SECURE_CORE = 1
    TOR = 2
    P2P = 4
    STREAMING = 8


class SplitTunnelingMode(str, Enum):
    EXCLUDE = "exclude"
    INCLUDE = "include"


class CustomDNSEntry:
    def __init__(self, address: str, enabled: bool):
        self.ip = ip_address(address)
        self.enabled = enabled

    @classmethod
    def new_from_string(cls, address: str, *, enabled: bool) -> CustomDNSEntry:
        return cls(address, enabled)


class BugReportForm:
    def __init__(self, **fields: Any):
        self.__dict__.update(fields)


class NPSSurveyResponse:
    class ResponseType(Enum):
        DISMISS = "dismiss"
        SUBMIT = "submit"

    def __init__(
        self,
        *,
        user_score: int,
        user_comments: str,
        response_type: ResponseType,
    ):
        self.user_score = user_score
        self.user_comments = user_comments
        self.response_type = response_type


def sort_servers_alphabetically_by_country_and_server_name(server: Any) -> str:
    server_name = (server.name or "").lower()
    if "#" in server_name:
        prefix, number = server_name.split("#", 1)
        server_name = f"{prefix}#{number.zfill(10)}"
    return f"{server.exit_country_name}__{server_name}"


def core_module_fakes() -> dict[str, ModuleType]:
    proton = ModuleType("proton")
    vpn = ModuleType("proton.vpn")
    core = ModuleType("proton.vpn.core")
    settings = ModuleType("proton.vpn.core.settings")
    split_tunneling = ModuleType("proton.vpn.core.settings.split_tunneling")
    session = ModuleType("proton.vpn.session")
    dataclasses = ModuleType("proton.vpn.session.dataclasses")
    servers = ModuleType("proton.vpn.session.servers")
    logicals = ModuleType("proton.vpn.session.servers.logicals")

    settings.CustomDNSEntry = CustomDNSEntry
    split_tunneling.SplitTunnelingMode = SplitTunnelingMode
    dataclasses.BugReportForm = BugReportForm
    dataclasses.NPSSurveyResponse = NPSSurveyResponse
    servers.ServerFeatureEnum = ServerFeatureEnum
    logicals.sort_servers_alphabetically_by_country_and_server_name = (
        sort_servers_alphabetically_by_country_and_server_name
    )

    proton.vpn = vpn
    vpn.core = core
    vpn.session = session
    core.settings = settings
    settings.split_tunneling = split_tunneling
    session.dataclasses = dataclasses
    session.servers = servers
    servers.logicals = logicals

    return {
        "proton": proton,
        "proton.vpn": vpn,
        "proton.vpn.core": core,
        "proton.vpn.core.settings": settings,
        "proton.vpn.core.settings.split_tunneling": split_tunneling,
        "proton.vpn.session": session,
        "proton.vpn.session.dataclasses": dataclasses,
        "proton.vpn.session.servers": servers,
        "proton.vpn.session.servers.logicals": logicals,
    }
