#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Reject broken repository-local links in Markdown documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


PROJECT_DIR = Path(__file__).resolve().parent.parent
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def local_target(raw_target: str) -> str | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith("#"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    return unquote(parsed.path)


def main() -> int:
    failures: list[str] = []
    for document in sorted(PROJECT_DIR.rglob("*.md")):
        if ".git" in document.parts:
            continue
        contents = document.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(contents):
            target = local_target(match.group(1))
            if target is None:
                continue
            destination = (document.parent / target).resolve()
            try:
                destination.relative_to(PROJECT_DIR)
            except ValueError:
                failures.append(
                    f"{document.relative_to(PROJECT_DIR)}: link leaves repository: "
                    f"{match.group(1)}"
                )
                continue
            if not destination.exists():
                failures.append(
                    f"{document.relative_to(PROJECT_DIR)}: missing link target: "
                    f"{match.group(1)}"
                )

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Documentation links are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
