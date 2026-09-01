#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bind the complete Fedora artifact set to one reviewed source commit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rpm_field(path: Path, query: str) -> str:
    return subprocess.run(
        ["rpm", "-qp", "--qf", query, str(path)],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()

    directory = args.artifact_directory.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        raise SystemExit("Source commit must be a complete lowercase Git object ID")
    artifacts = sorted(directory.glob("*.rpm"))
    if len(artifacts) != 6:
        raise SystemExit(f"Expected six RPM artifacts, found {len(artifacts)}")
    manifest_path = directory / "artifact-manifest.json"
    if manifest_path.exists():
        raise SystemExit(f"Refusing to replace existing manifest: {manifest_path}")

    source_names = {
        path.name
        for path in artifacts
        if rpm_field(path, "%{SOURCEPACKAGE}") == "1"
    }
    if len(source_names) != 3:
        raise SystemExit("Expected exactly three source RPMs")

    records = []
    for path in artifacts:
        source_package = rpm_field(path, "%{SOURCEPACKAGE}") == "1"
        source_rpm = "" if source_package else rpm_field(path, "%{SOURCERPM}")
        if source_rpm and source_rpm not in source_names:
            raise SystemExit(f"Missing paired source RPM for {path.name}: {source_rpm}")
        records.append(
            {
                "filename": path.name,
                "nevra": rpm_field(path, "%{NEVRA}"),
                "sha256": sha256(path),
                "size": path.stat().st_size,
                "sourcePackage": source_package,
                "sourceRpm": source_rpm,
            }
        )

    manifest = {
        "schemaVersion": 1,
        "sourceCommit": args.commit,
        "artifacts": records,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    if loaded != manifest:
        raise SystemExit("Artifact manifest readback differs from generated content")
    print(f"Bound six RPM artifacts to {args.commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
