#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Verify that the configured launcher scrubs unsafe variables before import."""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys
from types import ModuleType
from unittest import mock


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: check-backend-launcher-environment.py LAUNCHER CONTRACT"
        )

    launcher = Path(sys.argv[1]).resolve(strict=True)
    contract = Path(sys.argv[2]).resolve(strict=True)
    unsafe_names = tuple(
        line.strip()
        for line in contract.read_text(encoding="ascii").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not unsafe_names:
        raise RuntimeError("The staged environment contract is empty")

    captured: dict[str, str] = {}
    package = ModuleType("proton_vpn_kde_backend")
    package.__path__ = []  # type: ignore[attr-defined]
    entry_point = ModuleType("proton_vpn_kde_backend.__main__")
    entry_point.main = lambda: captured.update(os.environ)  # type: ignore[attr-defined]
    injected = {name: f"/tmp/attacker/{name}" for name in unsafe_names}
    injected.update(
        {
            "HOME": "/home/test",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "OPENSSL_CONFUSION": "/tmp/ordinary",
        }
    )

    with mock.patch.dict(os.environ, injected, clear=True), mock.patch.dict(
        sys.modules,
        {
            "proton_vpn_kde_backend": package,
            "proton_vpn_kde_backend.__main__": entry_point,
        },
    ):
        runpy.run_path(str(launcher), run_name="__main__")

    remaining = sorted(name for name in unsafe_names if name in captured)
    if remaining:
        raise RuntimeError(f"The launcher retained unsafe variables: {remaining}")
    if captured.get("HOME") != "/home/test":
        raise RuntimeError("The launcher removed an ordinary desktop variable")
    if captured.get("DBUS_SESSION_BUS_ADDRESS") != injected[
        "DBUS_SESSION_BUS_ADDRESS"
    ]:
        raise RuntimeError("The launcher removed the session bus address")
    if captured.get("OPENSSL_CONFUSION") != "/tmp/ordinary":
        raise RuntimeError("The launcher rejected a near-miss variable name")


if __name__ == "__main__":
    main()
