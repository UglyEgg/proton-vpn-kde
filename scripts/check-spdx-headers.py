#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Require SPDX provenance on project-authored source and build files."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COPYRIGHT = "SPDX-FileCopyrightText: 2026 Plasma VPN contributors"
LICENSE = "SPDX-License-Identifier: GPL-3.0-or-later"


def is_project_source(path: Path) -> bool:
    relative = path.relative_to(PROJECT_ROOT)
    name = relative.name
    if name == "CMakeLists.txt" or relative.as_posix() in {
        ".clang-tidy",
        ".editorconfig",
        ".gitattributes",
        ".gitignore",
    }:
        return True
    if name.endswith(".in"):
        return True
    return path.suffix in {
        ".cpp",
        ".desktop",
        ".h",
        ".json",
        ".notifyrc",
        ".py",
        ".qml",
        ".sh",
        ".spec",
        ".toml",
        ".xml",
        ".yml",
    }


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [
        PROJECT_ROOT / entry.decode("utf-8")
        for entry in result.stdout.split(b"\0")
        if entry
    ]


def main() -> int:
    missing: list[str] = []
    for path in tracked_files():
        if not is_project_source(path):
            continue
        header = "\n".join(path.read_text(encoding="utf-8").splitlines()[:8])
        if COPYRIGHT in header and LICENSE in header:
            continue
        sidecar = Path(f"{path}.license")
        if sidecar.is_file():
            annotation = sidecar.read_text(encoding="utf-8")
            if COPYRIGHT in annotation and LICENSE in annotation:
                continue
        missing.append(path.relative_to(PROJECT_ROOT).as_posix())

    if missing:
        print("Project source files missing SPDX provenance:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1
    print("SPDX source provenance is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
