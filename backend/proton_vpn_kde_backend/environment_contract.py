# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared unsafe process-environment contract for packaged peers."""

from __future__ import annotations

from pathlib import Path
import re


_ENVIRONMENT_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")


def _load_unsafe_environment_names() -> tuple[str, ...]:
    contract_path = Path(__file__).with_name("unsafe_environment.txt")
    names = tuple(
        line.strip()
        for line in contract_path.read_text(encoding="ascii").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not names:
        raise RuntimeError("The backend environment contract is empty")
    if len(names) != len(set(names)):
        raise RuntimeError("The backend environment contract contains duplicates")
    if any(_ENVIRONMENT_NAME.fullmatch(name) is None for name in names):
        raise RuntimeError("The backend environment contract contains an invalid name")
    return names


UNSAFE_ENVIRONMENT_NAMES = _load_unsafe_environment_names()
UNSAFE_ENVIRONMENT_PREFIXES = tuple(
    f"{name}=".encode("ascii") for name in UNSAFE_ENVIRONMENT_NAMES
)

__all__ = ["UNSAFE_ENVIRONMENT_NAMES", "UNSAFE_ENVIRONMENT_PREFIXES"]
