#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Reject trailing whitespace introduced into overlay target files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re
import sys


PROJECT_DIR = Path(__file__).resolve().parent.parent
PATCH_ROOT = PROJECT_DIR / "packaging" / "fedora"
HUNK_HEADER = re.compile(
    rb"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@(?: .*)?$"
)


def added_trailing_whitespace(lines: Iterable[bytes]) -> list[int]:
    """Return added-target line numbers with trailing horizontal whitespace."""
    failures: list[int] = []
    old_remaining = 0
    new_remaining = 0

    for line_number, line in enumerate(lines, 1):
        if line.startswith(b"@@"):
            if old_remaining or new_remaining:
                raise ValueError("A unified-diff hunk ended before its declared size")
            match = HUNK_HEADER.match(line)
            if match is None:
                raise ValueError(f"Malformed unified-diff hunk header at line {line_number}")
            old_remaining = int(match.group(1) or b"1")
            new_remaining = int(match.group(2) or b"1")
            continue
        if not old_remaining and not new_remaining:
            continue
        if line.startswith(b"\\ No newline at end of file"):
            continue

        marker = line[:1]
        if marker == b"+":
            target_line = line[1:]
            if target_line.rstrip(b" \t") != target_line:
                failures.append(line_number)
            new_remaining -= 1
        elif marker == b"-":
            old_remaining -= 1
        elif marker == b" " or not line:
            # Some of the upstream-generated payloads encode blank context as
            # an empty physical line; GNU patch accepts both representations.
            old_remaining -= 1
            new_remaining -= 1
        else:
            raise ValueError(f"Malformed unified-diff hunk line at {line_number}")
        if old_remaining < 0 or new_remaining < 0:
            raise ValueError(f"Unified-diff hunk exceeds its declared size at {line_number}")

    if old_remaining or new_remaining:
        raise ValueError("A unified-diff hunk ended before its declared size")
    return failures


def main() -> int:
    failures: list[str] = []
    patch_paths = sorted(PATCH_ROOT.glob("*-overlay/patches/*.patch"))
    for path in patch_paths:
        try:
            line_numbers = added_trailing_whitespace(
                path.read_bytes().splitlines()
            )
        except ValueError as error:
            failures.append(f"{path.relative_to(PROJECT_DIR)}: {error}")
            continue
        for line_number in line_numbers:
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
