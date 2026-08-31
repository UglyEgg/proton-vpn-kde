#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Rebuild and verify the narrow Proton VPN API Core RPM overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import py_compile
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any


class OverlayError(RuntimeError):
    """Raised when overlay provenance or payload verification fails."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OverlayError(f"Unable to read overlay manifest: {error}") from error

    if manifest.get("schemaVersion") != 1:
        raise OverlayError("Unsupported overlay manifest schema")
    if not isinstance(manifest.get("vendor"), dict):
        raise OverlayError("Overlay manifest has no vendor record")
    if not isinstance(manifest.get("overlay"), dict):
        raise OverlayError("Overlay manifest has no overlay record")
    return manifest


def _relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise OverlayError(f"Unsafe manifest path: {value!r}")
    return path


def _root_path(root: Path, value: str) -> Path:
    relative = _relative_path(value)
    return root.joinpath(*relative.parts)


def _run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment.update({"LC_ALL": "C", "TZ": "UTC"})
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


def _rpm_fields(path: Path) -> dict[str, str]:
    query = (
        "%{NEVRA}\n"
        "%{SOURCERPM}\n"
        "%{SHA256HEADER}\n"
        "%{PAYLOADSHA256}\n"
        "%{RSAHEADER:pgpsig}\n"
    )
    result = _run(["rpm", "-qp", "--qf", query, str(path)])
    values = result.stdout.decode("utf-8", errors="strict").splitlines()
    if len(values) != 5:
        raise OverlayError("Unexpected RPM provenance query result")
    return dict(
        zip(
            ("nevra", "sourceRpm", "headerSha256", "payloadSha256", "rsaHeader"),
            values,
            strict=True,
        )
    )


def verify_vendor_rpm(manifest: dict[str, Any], vendor_rpm: Path) -> None:
    vendor = manifest["vendor"]
    if vendor_rpm.name != vendor["rpmFilename"]:
        raise OverlayError(
            f"Expected vendor RPM {vendor['rpmFilename']}, got {vendor_rpm.name}"
        )
    actual_sha256 = _sha256(vendor_rpm)
    if actual_sha256 != vendor["rpmSha256"]:
        raise OverlayError(
            "Vendor RPM SHA-256 mismatch: "
            f"expected {vendor['rpmSha256']}, got {actual_sha256}"
        )

    fields = _rpm_fields(vendor_rpm)
    for field in (
        "nevra",
        "sourceRpm",
        "headerSha256",
        "payloadSha256",
        "rsaHeader",
    ):
        if fields[field] != vendor[field]:
            raise OverlayError(
                f"Vendor RPM {field} mismatch: "
                f"expected {vendor[field]!r}, got {fields[field]!r}"
            )

    _run(["rpmkeys", "--checksig", str(vendor_rpm)])


def _extract_rpm(rpm_path: Path, destination: Path) -> None:
    if destination.exists():
        raise OverlayError(f"Extraction destination already exists: {destination}")
    destination.mkdir(parents=True)

    converter = subprocess.Popen(
        ["rpm2cpio", str(rpm_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert converter.stdout is not None
    extractor = subprocess.run(
        ["cpio", "-idm", "--quiet"],
        cwd=destination,
        stdin=converter.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    converter.stdout.close()
    converter_stderr = converter.communicate()[1]
    if converter.returncode != 0:
        raise OverlayError(
            "Unable to decode RPM payload: "
            + converter_stderr.decode("utf-8", errors="replace").strip()
        )
    if extractor.returncode != 0:
        raise OverlayError(
            "Unable to extract RPM payload: "
            + extractor.stderr.decode("utf-8", errors="replace").strip()
        )


def _verify_patch_files(
    manifest: dict[str, Any], source_directory: Path
) -> list[Path]:
    source_directory = source_directory.resolve()
    patch_paths: list[Path] = []
    patches = manifest["overlay"].get("patches")
    if not isinstance(patches, list) or not patches:
        raise OverlayError("Overlay manifest has no applied patches")

    for patch_record in patches:
        filename = patch_record.get("file")
        if not isinstance(filename, str):
            raise OverlayError("Overlay patch record has no filename")
        patch_path = _root_path(source_directory, filename)
        if not patch_path.is_file():
            raise OverlayError(f"Missing overlay patch: {patch_path}")
        actual_sha256 = _sha256(patch_path)
        if actual_sha256 != patch_record.get("sha256"):
            raise OverlayError(
                f"Patch SHA-256 mismatch for {filename}: "
                f"expected {patch_record.get('sha256')}, got {actual_sha256}"
            )
        patch_paths.append(patch_path)
    return patch_paths


def _apply_patches(root: Path, patches: list[Path]) -> None:
    for patch_path in patches:
        _run(
            [
                "patch",
                "--batch",
                "--forward",
                "--fuzz=0",
                "-p1",
                "-i",
                str(patch_path),
            ],
            cwd=root,
        )


def _compile_derived_bytecode(manifest: dict[str, Any], root: Path) -> None:
    expected_tag = manifest["overlay"].get("pythonCacheTag")
    actual_tag = sys.implementation.cache_tag
    if actual_tag != expected_tag:
        raise OverlayError(
            f"Python cache tag mismatch: expected {expected_tag}, got {actual_tag}"
        )

    derived_files = manifest["overlay"].get("derivedBytecode")
    if not isinstance(derived_files, list):
        raise OverlayError("Overlay manifest has no derived-bytecode records")

    for record in derived_files:
        source_value = record.get("source")
        output_value = record.get("path")
        optimization = record.get("optimization")
        if (
            not isinstance(source_value, str)
            or not isinstance(output_value, str)
            or optimization not in (0, 1)
        ):
            raise OverlayError("Invalid derived-bytecode record")
        source = _root_path(root, source_value)
        output = _root_path(root, output_value)
        output.parent.mkdir(parents=True, exist_ok=True)
        py_compile.compile(
            str(source),
            cfile=str(output),
            dfile=f"/{_relative_path(source_value)}",
            doraise=True,
            optimize=optimization,
            invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH,
        )

    for record in derived_files:
        hardlink_value = record.get("hardlinkTo")
        if hardlink_value is None:
            continue
        if not isinstance(hardlink_value, str):
            raise OverlayError("Invalid derived-bytecode hardlink record")
        output = _root_path(root, record["path"])
        hardlink_target = _root_path(root, hardlink_value)
        if not output.is_file() or not hardlink_target.is_file():
            raise OverlayError("Derived-bytecode hardlink target is missing")
        if _sha256(output) != _sha256(hardlink_target):
            raise OverlayError(
                f"Derived bytecode differs from hardlink target: {output}"
            )
        output.unlink()
        os.link(hardlink_target, output)


def _copytree_preserving_hardlinks(source: Path, destination: Path) -> None:
    """Copy a payload without expanding RPM hardlink groups."""
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


def _tree_state(root: Path) -> dict[str, tuple[str, int, str]]:
    if not root.is_dir():
        raise OverlayError(f"Payload root does not exist: {root}")
    return {
        path.relative_to(root).as_posix(): _entry_state(path)
        for path in root.rglob("*")
    }


def _hardlink_groups(root: Path) -> set[tuple[str, ...]]:
    groups: dict[tuple[int, int], list[str]] = {}
    for path in root.rglob("*"):
        metadata = path.lstat()
        if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1:
            inode = (metadata.st_dev, metadata.st_ino)
            groups.setdefault(inode, []).append(path.relative_to(root).as_posix())
    return {tuple(sorted(paths)) for paths in groups.values() if len(paths) > 1}


def _verify_hardlink_topology(baseline_root: Path, overlay_root: Path) -> None:
    baseline_groups = _hardlink_groups(baseline_root)
    overlay_groups = _hardlink_groups(overlay_root)
    if baseline_groups != overlay_groups:
        removed = sorted(baseline_groups - overlay_groups)
        added = sorted(overlay_groups - baseline_groups)
        raise OverlayError(
            "Overlay changed payload hardlinks; "
            f"removed={removed}, added={added}"
        )


def _modified_file_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
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
    manifest: dict[str, Any], baseline_root: Path, overlay_root: Path
) -> None:
    baseline = _tree_state(baseline_root)
    overlay = _tree_state(overlay_root)
    if set(baseline) != set(overlay):
        added = sorted(set(overlay) - set(baseline))
        removed = sorted(set(baseline) - set(overlay))
        raise OverlayError(
            f"Overlay changed payload paths; added={added}, removed={removed}"
        )

    _verify_hardlink_topology(baseline_root, overlay_root)

    changed = {
        path for path in baseline if baseline[path] != overlay[path]
    }
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
            raise OverlayError(f"Modified payload entry is not a regular file: {path}")
        if baseline_mode != overlay_mode:
            raise OverlayError(f"Overlay changed file mode for {path}")
        if baseline_hash != record.get("vendorSha256"):
            raise OverlayError(
                f"Vendor installed-file hash mismatch for {path}: "
                f"expected {record.get('vendorSha256')}, got {baseline_hash}"
            )
        if overlay_hash != record.get("overlaySha256"):
            raise OverlayError(
                f"Overlay installed-file hash mismatch for {path}: "
                f"expected {record.get('overlaySha256')}, got {overlay_hash}"
            )


def prepare_overlay(
    manifest_path: Path,
    vendor_rpm: Path,
    source_directory: Path,
    baseline_root: Path,
    overlay_root: Path,
) -> None:
    manifest = _load_manifest(manifest_path)
    verify_vendor_rpm(manifest, vendor_rpm)
    patches = _verify_patch_files(manifest, source_directory)
    _extract_rpm(vendor_rpm, baseline_root)
    if overlay_root.exists():
        raise OverlayError(f"Overlay destination already exists: {overlay_root}")
    _copytree_preserving_hardlinks(baseline_root, overlay_root)
    _apply_patches(overlay_root, patches)
    _compile_derived_bytecode(manifest, overlay_root)
    verify_tree(manifest, baseline_root, overlay_root)
    print(
        "Verified API Core overlay: "
        f"{manifest['vendor']['nevra']} -> {manifest['overlay']['nevra']}; "
        f"{len(patches)} patches; "
        f"{len(_modified_file_records(manifest))} changed installed files"
    )


def verify_behavior(root: Path) -> None:
    site_packages = root / "usr/lib64/python3.14/site-packages"
    if not site_packages.is_dir():
        raise OverlayError(f"Missing staged site-packages: {site_packages}")
    sys.path.insert(0, str(site_packages))

    import gi  # noqa: PLC0415

    gi.require_version("NM", "1.0")
    from gi.repository import NM  # noqa: PLC0415

    from proton.vpn.core.cache_handler import CacheHandler  # noqa: PLC0415
    from proton.vpn.core.api import ProtonVPNAPI  # noqa: PLC0415
    from proton.vpn.backend.networkmanager.protocol.protun.protun import (  # noqa: PLC0415
        SYSTEM_OWNED_PRIVATE_KEY,
        PRIVATE_KEY,
        PRIVATE_KEY_FLAGS,
        ProtunUDP,
    )
    from proton.vpn.backend.networkmanager.core.nmclient import (  # noqa: PLC0415
        NMClient,
    )
    from proton.vpn.session.servers.logicals import (  # noqa: PLC0415
        _deduplicate_server_strings,
        _server_string_object_hook,
    )

    country_a = bytes((67, 72)).decode()
    country_b = bytes((67, 72)).decode()
    domain_a = bytes(b"node.example").decode()
    domain_b = bytes(b"node.example").decode()
    if country_a is country_b or domain_a is domain_b:
        raise OverlayError("Behavior fixture did not create distinct strings")

    logicals = [
        {"ExitCountry": country_a, "Servers": [{"Domain": domain_a}]},
        {"ExitCountry": country_b, "Servers": [{"Domain": domain_b}]},
    ]
    _deduplicate_server_strings(logicals)
    if logicals[0]["ExitCountry"] is not logicals[1]["ExitCountry"]:
        raise OverlayError("Fresh server-list strings were not shared")
    if logicals[0]["Servers"][0]["Domain"] is not logicals[1]["Servers"][0]["Domain"]:
        raise OverlayError("Fresh endpoint strings were not shared")

    with tempfile.TemporaryDirectory(prefix="proton-api-overlay-test.") as directory:
        cache_path = Path(directory) / "servers.json"
        cache_path.write_text(
            '{"LogicalServers": ['
            '{"ExitCountry": "CH", "Servers": [{"Domain": "node.example"}]},'
            '{"ExitCountry": "CH", "Servers": [{"Domain": "node.example"}]}'
            "]}",
            encoding="utf-8",
        )
        cached = CacheHandler(
            str(cache_path), object_hook_factory=_server_string_object_hook
        ).load()
    first, second = cached["LogicalServers"]
    if first["ExitCountry"] is not second["ExitCountry"]:
        raise OverlayError("Cached country strings were not shared during decode")
    if first["Servers"][0]["Domain"] is not second["Servers"][0]["Domain"]:
        raise OverlayError("Cached endpoint strings were not shared during decode")

    def deprecated_fido2_property_used(_api):
        raise OverlayError("supports_fido2 used the deprecated capability property")

    deprecated_property = ProtonVPNAPI.is_fido2_lib_available
    ProtonVPNAPI.is_fido2_lib_available = property(deprecated_fido2_property_used)
    try:
        for library_available, registered_key, expected in (
            (False, False, False),
            (False, True, False),
            (True, False, False),
            (True, True, True),
        ):
            api = object.__new__(ProtonVPNAPI)
            api._session_holder = SimpleNamespace(
                session=SimpleNamespace(
                    fido2_lib_available=library_available,
                    supports_fido2=registered_key,
                )
            )
            if api.supports_fido2 is not expected:
                raise OverlayError("Unexpected FIDO2 capability result")
    finally:
        ProtonVPNAPI.is_fido2_lib_available = deprecated_property

    class CapturingConnection:
        def add_setting(self, setting):
            self.setting = setting

    protocol = object.__new__(ProtunUDP)
    protocol.connection = CapturingConnection()
    protocol._vpnserver = SimpleNamespace(
        server_name="fixture",
        server_ip="192.0.2.1",
        x25519pk="public-fixture",
        wireguard_ports=SimpleNamespace(udp=[443]),
    )
    protocol._vpncredentials = SimpleNamespace(
        pubkey_credentials=SimpleNamespace(wg_private_key="private-fixture")
    )
    protocol._set_vpn_settings()
    vpn_setting = protocol.connection.setting
    if vpn_setting.get_secret(PRIVATE_KEY) != "private-fixture":
        raise OverlayError("Protun did not retain its activation-time private key")
    expected_secret_flag = str(int(NM.SettingSecretFlags.NONE))
    if SYSTEM_OWNED_PRIVATE_KEY != expected_secret_flag:
        raise OverlayError("Protun's private-key constant is not system-owned")
    if vpn_setting.get_data_item(PRIVATE_KEY_FLAGS) != expected_secret_flag:
        raise OverlayError("Protun private key is not system-owned")

    add_call = {}

    class CapturingNMClient:
        def add_connection_async(
            self, *, connection, save_to_disk, cancellable, callback, user_data
        ):
            add_call.update(
                connection=connection,
                save_to_disk=save_to_disk,
                cancellable=cancellable,
                callback=callback,
                user_data=user_data,
            )

    callback = object()
    future = object()
    nm_client = object.__new__(NMClient)
    nm_client._nm_client = CapturingNMClient()
    nm_client.create_nmcli_callback = lambda **_kwargs: (callback, future)
    nm_client._assert_running_on_main_loop_thread = lambda: None
    nm_client._run_on_main_loop_thread = lambda function: function()
    if nm_client.add_connection_async(protocol.connection) is not future:
        raise OverlayError("NetworkManager wrapper did not return its add future")
    if add_call.get("connection") is not protocol.connection:
        raise OverlayError("Protun did not add the generated VPN connection")
    if add_call.get("save_to_disk") is not False:
        raise OverlayError("Protun connection is not explicitly unsaved")
    print("Verified API Core overlay behavior")


def verify_overlay_rpm(
    manifest_path: Path, vendor_rpm: Path, overlay_rpm: Path
) -> None:
    manifest = _load_manifest(manifest_path)
    verify_vendor_rpm(manifest, vendor_rpm)
    overlay_fields = _rpm_fields(overlay_rpm)
    if overlay_fields["nevra"] != manifest["overlay"]["nevra"]:
        raise OverlayError(
            f"Overlay RPM NEVRA mismatch: expected {manifest['overlay']['nevra']}, "
            f"got {overlay_fields['nevra']}"
        )
    for option in ("--requires", "--obsoletes", "--conflicts"):
        vendor_values = sorted(
            _run(["rpm", "-qp", option, str(vendor_rpm)]).stdout.splitlines()
        )
        overlay_values = sorted(
            _run(["rpm", "-qp", option, str(overlay_rpm)]).stdout.splitlines()
        )
        if overlay_values != vendor_values:
            raise OverlayError(f"Overlay RPM metadata differs for {option}")
    vendor_scripts = _run(["rpm", "-qp", "--scripts", str(vendor_rpm)]).stdout
    overlay_scripts = _run(["rpm", "-qp", "--scripts", str(overlay_rpm)]).stdout
    if overlay_scripts != vendor_scripts:
        raise OverlayError("Overlay RPM scriptlets differ from the vendor RPM")
    with tempfile.TemporaryDirectory(prefix="proton-api-overlay-rpm.") as directory:
        temporary = Path(directory)
        baseline = temporary / "vendor"
        overlay = temporary / "overlay"
        _extract_rpm(vendor_rpm, baseline)
        _extract_rpm(overlay_rpm, overlay)
        verify_tree(manifest, baseline, overlay)
        verify_behavior(overlay)
    print(
        f"Verified built overlay RPM {_sha256(overlay_rpm)}  {overlay_rpm}"
    )


def verify_installed(manifest_path: Path) -> None:
    manifest = _load_manifest(manifest_path)
    package_name = manifest["overlay"]["packageName"]
    result = _run(["rpm", "-q", package_name, "--qf", "%{NEVRA}"])
    actual_nevra = result.stdout.decode("utf-8", errors="strict")
    if actual_nevra != manifest["overlay"]["nevra"]:
        raise OverlayError(
            f"Installed overlay NEVRA mismatch: expected "
            f"{manifest['overlay']['nevra']}, got {actual_nevra}"
        )
    for path, record in _modified_file_records(manifest).items():
        installed_path = Path("/") / path
        if not installed_path.is_file():
            raise OverlayError(f"Missing installed overlay file: /{path}")
        actual_hash = _sha256(installed_path)
        if actual_hash != record["overlaySha256"]:
            raise OverlayError(
                f"Installed overlay hash mismatch for /{path}: "
                f"expected {record['overlaySha256']}, got {actual_hash}"
            )
    print(f"Verified installed API Core overlay {actual_nevra}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--vendor-rpm", type=Path, required=True)
    prepare.add_argument("--source-directory", type=Path, required=True)
    prepare.add_argument("--baseline-root", type=Path, required=True)
    prepare.add_argument("--overlay-root", type=Path, required=True)

    verify = subparsers.add_parser("verify-tree")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--baseline-root", type=Path, required=True)
    verify.add_argument("--overlay-root", type=Path, required=True)

    behavior = subparsers.add_parser("verify-behavior")
    behavior.add_argument("--root", type=Path, required=True)

    rpm_parser = subparsers.add_parser("verify-rpm")
    rpm_parser.add_argument("--manifest", type=Path, required=True)
    rpm_parser.add_argument("--vendor-rpm", type=Path, required=True)
    rpm_parser.add_argument("--overlay-rpm", type=Path, required=True)

    installed = subparsers.add_parser("verify-installed")
    installed.add_argument("--manifest", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        if arguments.command == "prepare":
            prepare_overlay(
                arguments.manifest,
                arguments.vendor_rpm,
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
            print("Verified API Core overlay payload boundary")
        elif arguments.command == "verify-behavior":
            verify_behavior(arguments.root)
        elif arguments.command == "verify-rpm":
            verify_overlay_rpm(
                arguments.manifest,
                arguments.vendor_rpm,
                arguments.overlay_rpm,
            )
        elif arguments.command == "verify-installed":
            verify_installed(arguments.manifest)
        else:
            raise OverlayError(f"Unsupported command: {arguments.command}")
    except (OverlayError, OSError, py_compile.PyCompileError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
