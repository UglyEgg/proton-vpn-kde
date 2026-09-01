#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Reject trailing whitespace introduced into overlay target files."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parent.parent
PATCH_ROOT = PROJECT_DIR / "packaging" / "fedora"


def main() -> int:
    failures: list[str] = []
    patch_paths = sorted(PATCH_ROOT.glob("*-overlay/patches/*.patch"))
    for path in patch_paths:
        for line_number, line in enumerate(path.read_bytes().splitlines(), 1):
            if not line.startswith(b"+") or line.startswith(b"+++"):
                continue
            target_line = line[1:]
            if target_line.rstrip(b" \t") != target_line:
                failures.append(
                    f"{path.relative_to(PROJECT_DIR)}:{line_number}: "
                    "added target line has trailing whitespace"
                )

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Overlay patch additions are whitespace-clean ({len(patch_paths)} patches)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
