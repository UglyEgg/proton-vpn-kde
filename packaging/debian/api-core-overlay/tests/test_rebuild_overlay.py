# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
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
    def test_current_manifest_is_internally_consistent(self):
        manifest = rebuild_overlay._load_manifest(
            SCRIPT.parent / "overlay-manifest.json"
        )

        self.assertEqual("5.6.10", manifest["vendor"]["version"])
        self.assertEqual(
            "5.6.10-12plasmavpn1", manifest["overlay"]["packageVersion"]
        )
        self.assertEqual(
            "0004-keep-protun-private-key-ephemeral.patch",
            manifest["overlay"]["capabilityPatch"],
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
            "0003-avoid-deprecated-fido2-capability-query.patch",
            listed_names,
        )

    def test_manifest_rejects_an_unlisted_capability_patch(self):
        manifest_path = SCRIPT.parent / "overlay-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["overlay"]["capabilityPatch"] = "missing.patch"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                rebuild_overlay.OverlayError,
                "required capability is not tied to a listed patch",
            ):
                rebuild_overlay._load_manifest(path)

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
