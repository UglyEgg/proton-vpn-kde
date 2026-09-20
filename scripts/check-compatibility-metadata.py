#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep the tested runtime floors aligned across release metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib


PROJECT_DIR = Path(__file__).resolve().parent.parent
EXPECTED_PYTHON = "3.11"
EXPECTED_DEPENDENCIES = {
    "cryptography": "50.0.0",
    "dbus-fast": "2.20",
}
EXPECTED_UBUNTU_DEPENDENCIES = {
    "cryptography": "46.0.5",
    "dbus-fast": "2.20",
}


def fail(message: str) -> None:
    raise ValueError(message)


def project_metadata() -> tuple[str, dict[str, str]]:
    pyproject = tomllib.loads(
        (PROJECT_DIR / "backend/pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    requires_python = pyproject["requires-python"]
    dependencies: dict[str, str] = {}
    for dependency in pyproject["dependencies"]:
        match = re.fullmatch(r"([a-z0-9-]+)>=(.+)", dependency)
        if match is None:
            fail(f"unsupported project dependency form: {dependency}")
        dependencies[match.group(1)] = match.group(2)
    return requires_python, dependencies


def minimum_requirements() -> dict[str, str]:
    requirements = (
        PROJECT_DIR / "backend/requirements-minimum.txt"
    ).read_text(encoding="utf-8")
    return dict(re.findall(r"^([a-z0-9-]+)==([^ \\]+)", requirements, re.MULTILINE))


def normalized_version(version: str) -> tuple[int, ...]:
    parts = [int(part) for part in version.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def require_text(path: Path, pattern: str, label: str) -> None:
    if re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE) is None:
        fail(f"{label} is not aligned in {path.relative_to(PROJECT_DIR)}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_debian_overlay_patch_inputs(manifest: dict[str, object]) -> None:
    overlay = manifest.get("overlay")
    if not isinstance(overlay, dict):
        fail("Ubuntu Core overlay metadata is missing")
    patches = overlay.get("patches")
    if not isinstance(patches, list):
        fail("Ubuntu Core overlay patch list is missing")

    override_directory = (
        PROJECT_DIR / "packaging/debian/api-core-overlay/patches"
    )
    shared_directory = PROJECT_DIR / "packaging/fedora/api-core-overlay/patches"
    listed_names: set[str] = set()
    for record in patches:
        if not isinstance(record, dict):
            fail("Ubuntu Core overlay patch record is invalid")
        name = record.get("file")
        expected = record.get("sha256")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not name.endswith(".patch")
            or not isinstance(expected, str)
        ):
            fail("Ubuntu Core overlay patch metadata is invalid")
        if name in listed_names:
            fail(f"duplicate Ubuntu Core overlay patch: {name}")
        listed_names.add(name)
        override = override_directory / name
        source = override if override.is_file() else shared_directory / name
        if not source.is_file():
            fail(f"Ubuntu Core overlay patch input is missing: {name}")
        actual = sha256(source)
        if actual != expected:
            fail(
                f"Ubuntu Core overlay patch hash is stale for {name}: "
                f"expected {expected}, got {actual}"
            )

    unlisted_overrides = {
        path.name for path in override_directory.glob("*.patch")
    } - listed_names
    if unlisted_overrides:
        fail(
            "Ubuntu Core overlay contains unlisted patch overrides: "
            + ", ".join(sorted(unlisted_overrides))
        )


def check() -> None:
    requires_python, dependencies = project_metadata()
    if requires_python != f">={EXPECTED_PYTHON}":
        fail(f"expected Python >={EXPECTED_PYTHON}, found {requires_python}")

    if dependencies != EXPECTED_DEPENDENCIES:
        fail(
            "project dependency floors do not match the compatibility policy: "
            f"{dependencies}"
        )

    pinned = minimum_requirements()
    for name, version in EXPECTED_DEPENDENCIES.items():
        if name not in pinned or normalized_version(pinned[name]) != normalized_version(
            version
        ):
            fail(f"minimum test must pin {name}=={version}")

    floor_manifest = json.loads(
        (PROJECT_DIR / "packaging/fedora/core-compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    static_floor = floor_manifest["staticApiFloor"]["version"]
    runtime_floor = floor_manifest["runtimeFloor"]["version"]
    overlay_manifest = json.loads(
        (
            PROJECT_DIR
            / "packaging/fedora/api-core-overlay/overlay-manifest.json"
        ).read_text(encoding="utf-8")
    )
    overlay_version = overlay_manifest["vendor"]["version"]
    if normalized_version(static_floor) > normalized_version(runtime_floor):
        fail("static Core API floor is newer than the runtime floor")
    if normalized_version(runtime_floor) > normalized_version(overlay_version):
        fail("Core runtime floor is newer than the packaged overlay")

    overlay_spec = (
        PROJECT_DIR
        / "packaging/fedora/api-core-overlay/"
        "python3-proton-vpn-api-core-overlay.spec"
    )
    require_text(
        overlay_spec,
        rf"^Version:\s+{re.escape(overlay_version)}$",
        "Core overlay vendor version",
    )

    spec = PROJECT_DIR / "packaging/fedora/proton-vpn-kde.spec"
    require_text(
        spec,
        rf"^Requires:\s+python3-proton-vpn-api-core >= {re.escape(runtime_floor)}$",
        "Core runtime floor",
    )
    require_text(
        spec,
        r"^BuildRequires:\s+systemd-rpm-macros$",
        "systemd RPM macro build dependency",
    )
    for name, version in EXPECTED_DEPENDENCIES.items():
        rpm_name = "python3-dbus-fast" if name == "dbus-fast" else f"python3-{name}"
        require_text(
            spec,
            rf"^Requires:\s+{re.escape(rpm_name)}(?: >= {re.escape(version)})?$",
            f"{name} runtime dependency",
        )

    debian_control = PROJECT_DIR / "debian/control"
    debian_overlay_manifest = json.loads(
        (
            PROJECT_DIR
            / "packaging/debian/api-core-overlay/overlay-manifest.json"
        ).read_text(encoding="utf-8")
    )
    if debian_overlay_manifest["vendor"]["version"] != runtime_floor:
        fail("Ubuntu Core overlay does not match the supported runtime floor")
    check_debian_overlay_patch_inputs(debian_overlay_manifest)
    require_text(
        debian_control,
        rf"^\s+python3-proton-vpn-api-core \(>= {re.escape(runtime_floor)}\),$",
        "Debian Core runtime floor",
    )
    require_text(
        debian_control,
        r"^\s+proton-keyring-secret-service-provider-agnostic \(>= 1\),$",
        "Debian provider-neutral keyring capability",
    )
    require_text(
        debian_control,
        r"^\s+proton-keyring-secret-service-owner-pinned \(>= 1\),$",
        "Debian owner-pinned keyring capability",
    )
    require_text(
        debian_control,
        r"^\s+proton-vpn-api-core-plasma-protun-secret \(>= 1\),$",
        "Debian Protun Core capability",
    )
    for name, version in EXPECTED_UBUNTU_DEPENDENCIES.items():
        debian_name = "python3-dbus-fast" if name == "dbus-fast" else f"python3-{name}"
        require_text(
            debian_control,
            rf"^\s+{re.escape(debian_name)} \(>= {re.escape(version)}\),$",
            f"Debian {name} runtime dependency",
        )

    workflow = PROJECT_DIR / ".github/workflows/ci.yml"
    require_text(
        workflow,
        rf'^\s+python-version: "{re.escape(EXPECTED_PYTHON)}"$',
        "minimum CI Python version",
    )


def main() -> int:
    try:
        check()
    except (KeyError, OSError, ValueError) as error:
        print(f"Compatibility metadata check failed: {error}", file=sys.stderr)
        return 1
    print("Compatibility metadata is aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
