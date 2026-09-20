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
HUNK_HEADER = re.compile(
    rb"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@(?:[ \t].*)?$"
)


def patch_lines(data: bytes) -> list[bytes]:
    """Split patch bytes without treating embedded carriage returns as lines."""
    has_crlf = b"\r\n" in data
    without_crlf = data.replace(b"\r\n", b"")
    if b"\r" in without_crlf:
        raise ValueError("Bare carriage return in patch input")
    if has_crlf and b"\n" in without_crlf:
        raise ValueError("Mixed LF and CRLF line endings in patch input")

    normalized = data.replace(b"\r\n", b"\n") if has_crlf else data
    lines = normalized.split(b"\n")
    if normalized.endswith(b"\n"):
        # split() returns a sentinel after a terminal delimiter. It is not a
        # physical blank context line and must not satisfy a hunk count.
        lines.pop()
    return lines


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
    patch_paths = sorted(
        [
            *PROJECT_DIR.glob("packaging/fedora/*-overlay/patches/*.patch"),
            *PROJECT_DIR.glob("packaging/debian/*-overlay/patches/*.patch"),
        ]
    )
    for path in patch_paths:
        try:
            line_numbers = added_trailing_whitespace(
                patch_lines(path.read_bytes())
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
