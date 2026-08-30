#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep the tested runtime floors aligned across release metadata."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tomllib


PROJECT_DIR = Path(__file__).resolve().parent.parent
EXPECTED_PYTHON = "3.11"
EXPECTED_DEPENDENCIES = {
    "cryptography": "45.0.1",
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

    manifest = json.loads(
        (PROJECT_DIR / "packaging/fedora/core-compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    core_version = manifest["minimum"]["version"]

    spec = PROJECT_DIR / "packaging/fedora/proton-vpn-kde.spec"
    require_text(
        spec,
        rf"^Requires:\s+python3-proton-vpn-api-core >= {re.escape(core_version)}$",
        "Core runtime floor",
    )
    for name, version in EXPECTED_DEPENDENCIES.items():
        rpm_name = "python3-dbus-fast" if name == "dbus-fast" else f"python3-{name}"
        require_text(
            spec,
            rf"^Requires:\s+{re.escape(rpm_name)}(?: >= {re.escape(version)})?$",
            f"{name} runtime dependency",
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
