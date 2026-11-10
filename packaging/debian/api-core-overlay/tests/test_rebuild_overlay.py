# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "rebuild_overlay.py"
SPEC = importlib.util.spec_from_file_location("debian_rebuild_overlay", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
rebuild_overlay = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rebuild_overlay
SPEC.loader.exec_module(rebuild_overlay)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OverlayBoundaryTests(unittest.TestCase):
    def test_original_source_readme_retains_published_content(self):
        # README is part of the immutable 5.8.11 original archive, not the
        # Debian revision. Current build instructions live in docs/RELEASING.md.
        self.assertEqual(
            "5ff730bb6e4fcf1c9f9ae010e8d329aab1e413744865ab9d1dd84cfc8a547260",
            sha256(SCRIPT.parent / "README.md"),
        )

    def test_builder_rejects_changed_original_before_package_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "vendor.deb"
            vendor.write_bytes(b"not the published original-source input\n")
            tools = root / "bin"
            tools.mkdir()
            for name in ("curl", "dpkg-buildpackage", "dpkg-deb", "patch"):
                command = tools / name
                command.write_text(
                    "#!/bin/sh\necho 'Unexpected external tool invocation' >&2\nexit 77\n",
                    encoding="utf-8",
                )
                command.chmod(0o755)
            result = subprocess.run(
                ["bash", str(SCRIPT.parent / "build-overlay-deb.sh"),
                 str(root / "output"), str(vendor)],
                env={**os.environ, "PATH": f"{tools}:{os.environ['PATH']}"},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("Pinned original-source archive differs", result.stderr)
            self.assertNotIn("Unexpected external tool invocation", result.stderr)
            self.assertEqual([], list((root / "output").iterdir()))

    def test_current_manifest_is_internally_consistent(self):
        manifest = rebuild_overlay._load_manifest(
            SCRIPT.parent / "overlay-manifest.json"
        )

        self.assertEqual("5.8.11", manifest["vendor"]["version"])
        self.assertEqual(
            "5.8.11-1plasmavpn1", manifest["overlay"]["packageVersion"]
        )
        self.assertEqual(
            "vendor", manifest["overlay"]["capabilitySource"]["kind"],
        )
        self.assertEqual(6, len(manifest["overlay"]["modifiedFiles"]))

    def test_current_manifest_resolves_version_specific_patch_inputs(self):
        manifest = rebuild_overlay._load_manifest(
            SCRIPT.parent / "overlay-manifest.json"
        )
        shared_directory = (
            SCRIPT.parents[2] / "fedora/api-core-overlay/patches"
        )
        override_directory = SCRIPT.parent / "patches"
        listed_names = {
            record["file"] for record in manifest["overlay"]["patches"]
        }

        self.assertEqual(
            {record["file"] for record in manifest["overlay"]["patches"]},
            {path.name for path in override_directory.glob("*.patch")},
        )
        for record in manifest["overlay"]["patches"]:
            override = override_directory / record["file"]
            source = override if override.is_file() else shared_directory / record["file"]
            self.assertTrue(source.is_file(), record["file"])
            self.assertEqual(record["sha256"], sha256(source), record["file"])
        self.assertIn(
            "0002-avoid-deprecated-fido2-capability-query.patch",
            listed_names,
        )

    def test_manifest_rejects_an_unlisted_capability_patch(self):
        manifest_path = SCRIPT.parent / "overlay-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["overlay"]["capabilitySource"] = {"kind": "patch", "patch": "missing.patch"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                rebuild_overlay.OverlayError,
                "required capability is not tied to a listed patch",
            ):
                rebuild_overlay._load_manifest(path)

    def test_manifest_rejects_unsupported_vendor_capability_claims(self):
        path = SCRIPT.parent / "overlay-manifest.json"
        for source, message in (
            ({"kind": "vendor", "minimumVersion": "6.0", "evidence": "fixture"},
             "predates the required capability"),
            ({"kind": "vendor", "minimumVersion": "5.8.2", "evidence": " "},
             "has no evidence"),
            ({"kind": "vendor", "minimumVersion": "not-a-version", "evidence": "fixture"},
             "has no valid version"),
            ({"kind": "unknown"}, "unknown source"),
        ):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest["overlay"]["capabilitySource"] = source
                changed = Path(directory) / "manifest.json"
                changed.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(rebuild_overlay.OverlayError, message):
                    rebuild_overlay._load_manifest(changed)

    def test_allows_only_the_exact_manifest_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            overlay = root / "overlay"
            baseline.mkdir()
            (baseline / "allowed.py").write_text("vendor\n", encoding="utf-8")
            (baseline / "same.dat").write_bytes(b"same")
            shutil.copytree(baseline, overlay)
            (overlay / "allowed.py").write_text("overlay\n", encoding="utf-8")
            manifest = {
                "overlay": {
                    "modifiedFiles": [
                        {
                            "path": "allowed.py",
                            "vendorSha256": sha256(baseline / "allowed.py"),
                            "overlaySha256": sha256(overlay / "allowed.py"),
                        }
                    ]
                }
            }

            rebuild_overlay.verify_tree(manifest, baseline, overlay)

            (overlay / "same.dat").write_bytes(b"unexpected")
            with self.assertRaisesRegex(
                rebuild_overlay.OverlayError, "unexpected=.*same.dat"
            ):
                rebuild_overlay.verify_tree(manifest, baseline, overlay)

    @staticmethod
    def boot_unit_fixture(root):
        baseline, overlay = root / "baseline", root / "overlay"
        source = "lib/systemd/system/proton-vpn-kill-switch-boot.service"
        target = "usr/lib/systemd/system/proton-vpn-kill-switch-boot.service"
        (baseline / source).parent.mkdir(parents=True)
        (baseline / "usr/lib").mkdir(parents=True)
        for path in baseline.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
        (baseline / source).write_bytes(b"unit fixture\n")
        (baseline / source).chmod(0o644)
        (baseline / "allowed.py").write_bytes(b"vendor\n")
        shutil.copytree(baseline, overlay)
        (overlay / "allowed.py").write_bytes(b"overlay\n")
        manifest = {"overlay": {
            "modifiedFiles": [{"path": "allowed.py", "vendorSha256": sha256(baseline / "allowed.py"),
                               "overlaySha256": sha256(overlay / "allowed.py")}],
            "bootUnitRelocation": {"vendorPath": source, "installedPath": target,
                                   "mode": "0644", "sha256": sha256(baseline / source)},
        }}
        return baseline, overlay, manifest, source, target

    def test_boot_unit_relocation_preserves_exact_payload_boundary(self):
        for mutation in ("bytes", "mode", "alias", "unrelated"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                baseline, overlay, manifest, source, target = self.boot_unit_fixture(Path(directory))
                rebuild_overlay._relocate_boot_unit(manifest, overlay)
                self.assertFalse((overlay / source).exists())
                self.assertEqual((baseline / source).read_bytes(), (overlay / target).read_bytes())
                rebuild_overlay.verify_tree(manifest, baseline, overlay)
                if mutation == "bytes":
                    (overlay / target).write_bytes(b"changed unit\n")
                elif mutation == "mode":
                    (overlay / target).chmod(0o755)
                elif mutation == "alias":
                    (overlay / source).parent.mkdir(parents=True)
                    (overlay / source).write_bytes(b"duplicate unit\n")
                else:
                    (overlay / "unexpected.dat").write_bytes(b"unrelated\n")
                with self.assertRaises(rebuild_overlay.OverlayError):
                    rebuild_overlay.verify_tree(manifest, baseline, overlay)

    def test_boot_unit_relocation_rejects_vendor_drift_and_target_collision(self):
        for mutation in ("vendor", "collision"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                _, overlay, manifest, source, target = self.boot_unit_fixture(Path(directory))
                if mutation == "vendor":
                    (overlay / source).write_bytes(b"changed vendor unit\n")
                else:
                    (overlay / target).parent.mkdir(parents=True)
                    (overlay / target).write_bytes(b"existing target\n")
                before = rebuild_overlay._tree_state(overlay)
                with self.assertRaises(rebuild_overlay.OverlayError):
                    rebuild_overlay._relocate_boot_unit(manifest, overlay)
                self.assertEqual(before, rebuild_overlay._tree_state(overlay))

    def test_manifest_rejects_arbitrary_boot_unit_relocation(self):
        manifest = json.loads((SCRIPT.parent / "overlay-manifest.json").read_text())
        manifest["overlay"]["bootUnitRelocation"]["installedPath"] = "etc/arbitrary.service"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(rebuild_overlay.OverlayError, "exact boot-unit relocation"):
                rebuild_overlay._load_manifest(path)

    def test_rejects_added_or_removed_payload_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            overlay = root / "overlay"
            baseline.mkdir()
            (baseline / "allowed.py").write_text("vendor\n", encoding="utf-8")
            shutil.copytree(baseline, overlay)
            (overlay / "added.py").write_text("unexpected\n", encoding="utf-8")
            manifest = {
                "overlay": {
                    "modifiedFiles": [
                        {
                            "path": "allowed.py",
                            "vendorSha256": sha256(baseline / "allowed.py"),
                            "overlaySha256": "unused",
                        }
                    ]
                }
            }

            with self.assertRaisesRegex(
                rebuild_overlay.OverlayError, "added=.*added.py"
            ):
                rebuild_overlay.verify_tree(manifest, baseline, overlay)

            (overlay / "added.py").unlink()
            (overlay / "allowed.py").unlink()
            with self.assertRaisesRegex(
                rebuild_overlay.OverlayError, "removed=.*allowed.py"
            ):
                rebuild_overlay.verify_tree(manifest, baseline, overlay)

    def test_payload_copy_preserves_hardlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            overlay = root / "overlay"
            baseline.mkdir()
            first = baseline / "first.so"
            second = baseline / "second.so"
            first.write_bytes(b"compiled payload")
            second.hardlink_to(first)

            rebuild_overlay._copytree_preserving_hardlinks(baseline, overlay)

            self.assertEqual(
                (overlay / "first.so").stat().st_ino,
                (overlay / "second.so").stat().st_ino,
            )

    def test_rejects_paths_outside_the_payload_root(self):
        with self.assertRaises(rebuild_overlay.OverlayError):
            rebuild_overlay._relative_path("../outside")
        with self.assertRaises(rebuild_overlay.OverlayError):
            rebuild_overlay._relative_path("/absolute")


if __name__ == "__main__":
    unittest.main()
