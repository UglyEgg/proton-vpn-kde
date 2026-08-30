#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify the public Proton Core surface consumed by the backend adapter."""

from __future__ import annotations

import argparse
import ast
from email.parser import Parser
from pathlib import Path
import sys


def parse_module(site_packages: Path, relative_path: str) -> ast.Module:
    path = site_packages / relative_path
    if not path.is_file():
        raise ValueError(f"missing Core module: {relative_path}")
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def exported_names(module: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in module.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.rsplit(".", 1)[-1])
    return names


def class_members(module: ast.Module, class_name: str) -> set[str]:
    class_node = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ),
        None,
    )
    if class_node is None:
        raise ValueError(f"missing Core class: {class_name}")

    members = {
        node.name
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in ast.walk(class_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            members.add(node.attr)
    return members


def require_names(label: str, available: set[str], required: set[str]) -> None:
    missing = sorted(required - available)
    if missing:
        raise ValueError(f"{label} is missing: {', '.join(missing)}")


def discover_site_packages(root: Path) -> Path:
    candidates = sorted(
        root.glob("usr/lib*/python*/site-packages/proton/vpn/core/api.py")
    )
    if len(candidates) != 1:
        raise ValueError(
            "expected one extracted Proton Core site-packages tree, "
            f"found {len(candidates)}"
        )
    return candidates[0].parents[3]


def verify_version(site_packages: Path, expected_version: str) -> None:
    metadata_files = sorted(
        site_packages.glob("proton_vpn_api_core-*.dist-info/METADATA")
    )
    if len(metadata_files) != 1:
        raise ValueError(
            "expected one Proton Core distribution metadata file, "
            f"found {len(metadata_files)}"
        )
    metadata = Parser().parsestr(metadata_files[0].read_text(encoding="utf-8"))
    if metadata.get("Version") != expected_version:
        raise ValueError(
            f"expected Core {expected_version}, found {metadata.get('Version', '')}"
        )


def verify_contract(site_packages: Path) -> None:
    api = parse_module(site_packages, "proton/vpn/core/api.py")
    require_names(
        "ProtonVPNAPI",
        class_members(api, "ProtonVPNAPI"),
        {
            "account_data",
            "account_name",
            "generate_2fa_fido2_assertion",
            "get_vpn_connector",
            "is_user_logged_in",
            "load_settings",
            "login",
            "logout",
            "refresher",
            "save_settings",
            "set_notification_seen",
            "submit_2fa_code",
            "submit_2fa_fido2",
            "submit_bug_report",
            "submit_nps_response",
            "supports_fido2",
        },
    )

    refresher = parse_module(
        site_packages, "proton/vpn/core/refresher/vpn_data_refresher.py"
    )
    require_names(
        "VPNDataRefresher",
        class_members(refresher, "VPNDataRefresher"),
        {
            "client_config",
            "disable",
            "enable",
            "feature_flags",
            "get_up_to_date_client_config",
            "get_up_to_date_server_list",
            "notifications",
            "server_list",
            "set_server_list_updated_callback",
            "set_server_loads_updated_callback",
        },
    )

    connector = parse_module(site_packages, "proton/vpn/core/vpnconnector.py")
    require_names(
        "VPNConnector",
        class_members(connector, "VPNConnector"),
        {
            "connect",
            "current_connection",
            "current_state",
            "disconnect",
            "get_vpn_server",
            "is_split_tunneling_available",
            "iter_available_protocols",
            "register",
            "unregister",
        },
    )

    exports = {
        "proton/vpn/core/session_holder.py": {"ClientTypeMetadata"},
        "proton/vpn/core/settings/__init__.py": {"CustomDNSEntry"},
        "proton/vpn/core/settings/split_tunneling.py": {"SplitTunnelingMode"},
        "proton/vpn/session/dataclasses/__init__.py": {
            "BugReportForm",
            "NPSSurveyResponse",
        },
        "proton/vpn/session/servers/__init__.py": {"ServerFeatureEnum"},
    }
    for module_path, required in exports.items():
        require_names(
            module_path,
            exported_names(parse_module(site_packages, module_path)),
            required,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    try:
        site_packages = discover_site_packages(args.root.resolve())
        verify_version(site_packages, args.expected_version)
        verify_contract(site_packages)
    except (OSError, SyntaxError, ValueError) as error:
        print(f"Core compatibility check failed: {error}", file=sys.stderr)
        return 1
    print(f"Proton Core {args.expected_version} public adapter contract is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
