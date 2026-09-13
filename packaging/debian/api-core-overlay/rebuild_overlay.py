#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Reconstruct and verify the Ubuntu Proton VPN API-Core overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


class OverlayError(RuntimeError):
    """Raised when a vendor or reconstructed payload violates the manifest."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise OverlayError(f"Unsafe manifest path: {value!r}")
    return path


def _root_path(root: Path, value: str) -> Path:
    relative = _relative_path(value)
    return root.joinpath(*relative.parts)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OverlayError(f"Unable to read overlay manifest: {error}") from error

    if manifest.get("schemaVersion") != 1:
        raise OverlayError("Unsupported Debian overlay manifest schema")
    vendor = manifest.get("vendor")
    overlay = manifest.get("overlay")
    if not isinstance(vendor, dict) or not isinstance(overlay, dict):
        raise OverlayError("Overlay manifest is missing vendor or overlay metadata")
    version = vendor.get("version")
    if not isinstance(version, str) or re.fullmatch(
        r"[0-9]+(?:\.[0-9]+)+", version
    ) is None:
        raise OverlayError("Vendor version is invalid")
    package_version = overlay.get("packageVersion")
    if not isinstance(package_version, str) or not package_version.startswith(
        f"{version}-"
    ):
        raise OverlayError("Overlay package version does not extend the vendor version")
    patches = overlay.get("patches")
    if not isinstance(patches, list) or not patches:
        raise OverlayError("Overlay manifest has no patches")
    patch_names = {
        record.get("file") for record in patches if isinstance(record, dict)
    }
    if overlay.get("capabilityPatch") not in patch_names:
        raise OverlayError("The required capability is not tied to a listed patch")
    _modified_file_records(manifest)
    return manifest


def _run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment.update({"LC_ALL": "C.UTF-8", "TZ": "UTC"})
    process = subprocess.run(
        arguments,
        cwd=cwd,
        env=environment,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        raise OverlayError(
            f"Command failed ({process.returncode}): {' '.join(arguments)}"
            + (f"\n{stderr}" if stderr else "")
        )
    return process


def _deb_field(path: Path, field: str) -> str:
    result = _run(["dpkg-deb", "--field", str(path), field])
    return result.stdout.decode("utf-8", errors="strict").strip()


def verify_vendor_deb(manifest: dict[str, Any], vendor_deb: Path) -> None:
    vendor = manifest["vendor"]
    if vendor_deb.name != vendor["filename"]:
        raise OverlayError(
            f"Expected vendor package {vendor['filename']}, got {vendor_deb.name}"
        )
    actual_sha256 = _sha256(vendor_deb)
    if actual_sha256 != vendor["sha256"]:
        raise OverlayError(
            "Vendor package SHA-256 mismatch: "
            f"expected {vendor['sha256']}, got {actual_sha256}"
        )
    for field, expected in (
        ("Package", vendor["package"]),
        ("Version", vendor["version"]),
        ("Architecture", vendor["architecture"]),
    ):
        actual = _deb_field(vendor_deb, field)
        if actual != expected:
            raise OverlayError(
                f"Vendor {field} mismatch: expected {expected!r}, got {actual!r}"
            )

    with tempfile.TemporaryDirectory(prefix="proton-vendor-deb-control.") as value:
        control_dir = Path(value) / "control"
        _run(["dpkg-deb", "--control", str(vendor_deb), str(control_dir)])
        control = control_dir / "control"
        if _sha256(control) != vendor["controlSha256"]:
            raise OverlayError("Vendor control metadata SHA-256 mismatch")
        for name, expected in vendor["maintainerScripts"].items():
            path = control_dir / name
            if not path.is_file() or _sha256(path) != expected:
                raise OverlayError(f"Vendor maintainer script mismatch: {name}")


def _extract_deb(path: Path, destination: Path) -> None:
    if destination.exists():
        raise OverlayError(f"Extraction destination already exists: {destination}")
    _run(["dpkg-deb", "--extract", str(path), str(destination)])


def _copytree_preserving_hardlinks(source: Path, destination: Path) -> None:
    copied_inodes: dict[tuple[int, int], Path] = {}

    def copy_file(source_value: str, destination_value: str) -> str:
        source_path = Path(source_value)
        destination_path = Path(destination_value)
        metadata = source_path.stat(follow_symlinks=False)
        inode = (metadata.st_dev, metadata.st_ino)
        existing = copied_inodes.get(inode)
        if metadata.st_nlink > 1 and existing is not None:
            os.link(existing, destination_path)
            return str(destination_path)
        shutil.copy2(source_path, destination_path, follow_symlinks=False)
        if metadata.st_nlink > 1:
            copied_inodes[inode] = destination_path
        return str(destination_path)

    shutil.copytree(
        source,
        destination,
        symlinks=True,
        copy_function=copy_file,
    )


def _verify_patch_files(
    manifest: dict[str, Any], source_directory: Path
) -> list[Path]:
    patch_paths: list[Path] = []
    for record in manifest["overlay"]["patches"]:
        filename = record.get("file")
        if not isinstance(filename, str):
            raise OverlayError("Overlay patch record has no filename")
        patch_path = source_directory / "patches" / filename
        if not patch_path.is_file():
            raise OverlayError(f"Missing overlay patch: {filename}")
        actual_sha256 = _sha256(patch_path)
        if actual_sha256 != record.get("sha256"):
            raise OverlayError(
                f"Patch SHA-256 mismatch for {filename}: "
                f"expected {record.get('sha256')}, got {actual_sha256}"
            )
        patch_paths.append(patch_path)
    return patch_paths


def _apply_patches(
    manifest: dict[str, Any], root: Path, patches: list[Path]
) -> None:
    prefixes = manifest["overlay"]["patchPathPrefix"]
    old_prefix = prefixes["from"].encode()
    new_prefix = prefixes["to"].encode()
    for patch_path in patches:
        patch_data = patch_path.read_bytes()
        if old_prefix not in patch_data:
            raise OverlayError(
                f"Patch has no expected Fedora path prefix: {patch_path.name}"
            )
        transformed = patch_data.replace(old_prefix, new_prefix)
        _run(
            ["patch", "--batch", "--forward", "--fuzz=0", "-p1"],
            cwd=root,
            input_data=transformed,
        )


def _entry_state(path: Path) -> tuple[str, int, str]:
    metadata = path.lstat()
    mode = stat.S_IMODE(metadata.st_mode)
    if stat.S_ISREG(metadata.st_mode):
        return ("file", mode, _sha256(path))
    if stat.S_ISDIR(metadata.st_mode):
        return ("directory", mode, "")
    if stat.S_ISLNK(metadata.st_mode):
        return ("symlink", mode, os.readlink(path))
    raise OverlayError(f"Unsupported payload entry type: {path}")


def _tree_state(
    root: Path, *, exclude_documentation: bool = False
) -> dict[str, tuple[str, int, str]]:
    if not root.is_dir():
        raise OverlayError(f"Payload root does not exist: {root}")
    result: dict[str, tuple[str, int, str]] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if exclude_documentation and (
            relative == "usr/share/doc" or relative.startswith("usr/share/doc/")
        ):
            continue
        result[relative] = _entry_state(path)
    return result


def _modified_file_records(
    manifest: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    records = manifest["overlay"].get("modifiedFiles")
    if not isinstance(records, list) or not records:
        raise OverlayError("Overlay manifest has no modified-file records")
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        value = record.get("path")
        if not isinstance(value, str):
            raise OverlayError("Modified-file record has no path")
        normalized = _relative_path(value).as_posix()
        if normalized in result:
            raise OverlayError(f"Duplicate modified-file record: {normalized}")
        result[normalized] = record
    return result


def verify_tree(
    manifest: dict[str, Any],
    baseline_root: Path,
    overlay_root: Path,
    *,
    exclude_documentation: bool = False,
) -> None:
    baseline = _tree_state(
        baseline_root, exclude_documentation=exclude_documentation
    )
    overlay = _tree_state(
        overlay_root, exclude_documentation=exclude_documentation
    )
    if set(baseline) != set(overlay):
        added = sorted(set(overlay) - set(baseline))
        removed = sorted(set(baseline) - set(overlay))
        raise OverlayError(
            f"Overlay changed payload paths; added={added}, removed={removed}"
        )

    changed = {path for path in baseline if baseline[path] != overlay[path]}
    expected = _modified_file_records(manifest)
    if changed != set(expected):
        unexpected = sorted(changed - set(expected))
        missing = sorted(set(expected) - changed)
        raise OverlayError(
            f"Overlay change set mismatch; unexpected={unexpected}, missing={missing}"
        )

    for path, record in expected.items():
        baseline_kind, baseline_mode, baseline_hash = baseline[path]
        overlay_kind, overlay_mode, overlay_hash = overlay[path]
        if baseline_kind != "file" or overlay_kind != "file":
            raise OverlayError(f"Modified payload entry is not a file: {path}")
        if baseline_mode != overlay_mode:
            raise OverlayError(f"Overlay changed file mode for {path}")
        if baseline_hash != record.get("vendorSha256"):
            raise OverlayError(f"Vendor installed-file hash mismatch for {path}")
        if overlay_hash != record.get("overlaySha256"):
            raise OverlayError(f"Overlay installed-file hash mismatch for {path}")


def prepare_overlay(
    manifest_path: Path,
    vendor_deb: Path,
    source_directory: Path,
    baseline_root: Path,
    overlay_root: Path,
) -> None:
    manifest = _load_manifest(manifest_path)
    verify_vendor_deb(manifest, vendor_deb)
    patches = _verify_patch_files(manifest, source_directory)
    _extract_deb(vendor_deb, baseline_root)
    if overlay_root.exists():
        raise OverlayError(f"Overlay destination already exists: {overlay_root}")
    _copytree_preserving_hardlinks(baseline_root, overlay_root)
    _apply_patches(manifest, overlay_root, patches)
    verify_tree(manifest, baseline_root, overlay_root)
    print(
        "Verified Debian API-Core overlay: "
        f"{manifest['vendor']['version']} -> "
        f"{manifest['overlay']['packageVersion']}; "
        f"{len(patches)} patches; "
        f"{len(_modified_file_records(manifest))} changed installed files"
    )


def verify_overlay_deb(
    manifest_path: Path, vendor_deb: Path, overlay_deb: Path
) -> None:
    manifest = _load_manifest(manifest_path)
    verify_vendor_deb(manifest, vendor_deb)
    for field, expected in (
        ("Package", manifest["vendor"]["package"]),
        ("Version", manifest["overlay"]["packageVersion"]),
        ("Architecture", manifest["vendor"]["architecture"]),
    ):
        actual = _deb_field(overlay_deb, field)
        if actual != expected:
            raise OverlayError(
                f"Overlay {field} mismatch: expected {expected!r}, got {actual!r}"
            )
    capability = manifest["overlay"]["capability"]
    if capability not in _deb_field(overlay_deb, "Provides"):
        raise OverlayError(f"Overlay package does not provide {capability}")

    with tempfile.TemporaryDirectory(prefix="proton-api-deb-verify.") as value:
        root = Path(value)
        baseline = root / "vendor"
        overlay = root / "overlay"
        _extract_deb(vendor_deb, baseline)
        _extract_deb(overlay_deb, overlay)
        verify_tree(
            manifest,
            baseline,
            overlay,
            exclude_documentation=True,
        )
    print(f"Verified built Debian API-Core overlay: {_sha256(overlay_deb)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--vendor-deb", type=Path, required=True)
    prepare.add_argument("--source-directory", type=Path, required=True)
    prepare.add_argument("--baseline-root", type=Path, required=True)
    prepare.add_argument("--overlay-root", type=Path, required=True)

    verify = subparsers.add_parser("verify-tree")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--baseline-root", type=Path, required=True)
    verify.add_argument("--overlay-root", type=Path, required=True)

    verify_deb = subparsers.add_parser("verify-deb")
    verify_deb.add_argument("--manifest", type=Path, required=True)
    verify_deb.add_argument("--vendor-deb", type=Path, required=True)
    verify_deb.add_argument("--overlay-deb", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        if arguments.command == "prepare":
            prepare_overlay(
                arguments.manifest,
                arguments.vendor_deb,
                arguments.source_directory,
                arguments.baseline_root,
                arguments.overlay_root,
            )
        elif arguments.command == "verify-tree":
            verify_tree(
                _load_manifest(arguments.manifest),
                arguments.baseline_root,
                arguments.overlay_root,
            )
            print("Verified Debian API-Core overlay payload boundary")
        elif arguments.command == "verify-deb":
            verify_overlay_deb(
                arguments.manifest,
                arguments.vendor_deb,
                arguments.overlay_deb,
            )
        else:
            raise OverlayError(f"Unsupported command: {arguments.command}")
    except (KeyError, OSError, OverlayError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
