#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bind a complete Fedora or Ubuntu artifact set to one source commit."""

from __future__ import annotations

import argparse
from collections import Counter
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


def deb_field(path: Path, field: str) -> str:
    return subprocess.run(
        ["dpkg-deb", "--field", str(path), field],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def debian_artifact_type(path: Path) -> str:
    suffixes = (
        (".ddeb", "debug-symbol"),
        (".deb", "binary"),
        (".dsc", "source-control"),
        (".buildinfo", "build-info"),
        (".changes", "changes"),
        (".orig.tar.gz", "upstream-source"),
        (".debian.tar.xz", "debian-source"),
    )
    for suffix, artifact_type in suffixes:
        if path.name.endswith(suffix):
            return artifact_type
    raise SystemExit(f"Unexpected Debian release artifact: {path.name}")


def debian_source_name(path: Path) -> str:
    return path.name.split("_", maxsplit=1)[0]


def debian_records(directory: Path) -> list[dict[str, object]]:
    artifacts = sorted(path for path in directory.iterdir() if path.is_file())
    if len(artifacts) != 19:
        raise SystemExit(f"Expected 19 Debian artifacts, found {len(artifacts)}")

    artifact_types = {path: debian_artifact_type(path) for path in artifacts}
    expected_counts = Counter(
        {
            "binary": 3,
            "debug-symbol": 1,
            "source-control": 3,
            "build-info": 3,
            "changes": 3,
            "upstream-source": 3,
            "debian-source": 3,
        }
    )
    actual_counts = Counter(artifact_types.values())
    if actual_counts != expected_counts:
        raise SystemExit(
            "Unexpected Debian artifact composition: "
            f"expected {dict(expected_counts)}, found {dict(actual_counts)}"
        )

    binary_identity = {
        (
            deb_field(path, "Package"),
            deb_field(path, "Architecture"),
            artifact_types[path],
        )
        for path in artifacts
        if artifact_types[path] in {"binary", "debug-symbol"}
    }
    expected_binary_identity = {
        ("proton-vpn-kde", "amd64", "binary"),
        ("python3-proton-keyring-linux", "all", "binary"),
        ("python3-proton-vpn-api-core", "amd64", "binary"),
        ("proton-vpn-kde-dbgsym", "amd64", "debug-symbol"),
    }
    if binary_identity != expected_binary_identity:
        raise SystemExit(
            "Unexpected Debian binary package set: "
            f"expected {sorted(expected_binary_identity)}, "
            f"found {sorted(binary_identity)}"
        )

    expected_sources = {
        "proton-keyring-linux",
        "proton-vpn-api-core",
        "proton-vpn-kde",
    }
    for artifact_type in {
        "source-control",
        "build-info",
        "changes",
        "upstream-source",
        "debian-source",
    }:
        source_names = {
            debian_source_name(path)
            for path in artifacts
            if artifact_types[path] == artifact_type
        }
        if source_names != expected_sources:
            raise SystemExit(
                f"Unexpected {artifact_type} source set: "
                f"expected {sorted(expected_sources)}, found {sorted(source_names)}"
            )

    records: list[dict[str, object]] = []
    for path in artifacts:
        record: dict[str, object] = {
            "artifactType": artifact_types[path],
            "filename": path.name,
            "sha256": sha256(path),
            "size": path.stat().st_size,
        }
        if artifact_types[path] in {"binary", "debug-symbol"}:
            record.update(
                {
                    "architecture": deb_field(path, "Architecture"),
                    "package": deb_field(path, "Package"),
                    "version": deb_field(path, "Version"),
                }
            )
        else:
            record["sourceName"] = debian_source_name(path)
        records.append(record)
    return records


def rpm_records(directory: Path) -> list[dict[str, object]]:
    artifacts = sorted(directory.glob("*.rpm"))
    if len(artifacts) != 6:
        raise SystemExit(f"Expected six RPM artifacts, found {len(artifacts)}")

    source_names = {
        path.name
        for path in artifacts
        if rpm_field(path, "%{SOURCEPACKAGE}") == "1"
    }
    if len(source_names) != 3:
        raise SystemExit("Expected exactly three source RPMs")

    records: list[dict[str, object]] = []
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
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()

    directory = args.artifact_directory.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        raise SystemExit("Source commit must be a complete lowercase Git object ID")
    manifest_path = directory / "artifact-manifest.json"
    if manifest_path.exists():
        raise SystemExit(f"Refusing to replace existing manifest: {manifest_path}")

    rpm_artifacts = list(directory.glob("*.rpm"))
    debian_artifacts = list(directory.glob("*.deb"))
    if rpm_artifacts and debian_artifacts:
        raise SystemExit("Refusing to mix Fedora and Debian release artifacts")
    if rpm_artifacts:
        records = rpm_records(directory)
        artifact_set = "six RPM"
    elif debian_artifacts:
        records = debian_records(directory)
        artifact_set = "19 Debian"
    else:
        raise SystemExit("No RPM or Debian release artifacts found")

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
    print(f"Bound {artifact_set} artifacts to {args.commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
