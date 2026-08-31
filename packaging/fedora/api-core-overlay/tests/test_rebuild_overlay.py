# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "rebuild_overlay.py"
SPEC = importlib.util.spec_from_file_location("rebuild_overlay", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
rebuild_overlay = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rebuild_overlay
SPEC.loader.exec_module(rebuild_overlay)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OverlayBoundaryTests(unittest.TestCase):
    def test_external_provenance_queries_use_a_stable_locale_and_timezone(self):
        completed = rebuild_overlay.subprocess.CompletedProcess(
            ["true"], 0, stdout=b"", stderr=b""
        )
        with mock.patch.object(
            rebuild_overlay.subprocess, "run", return_value=completed
        ) as run:
            rebuild_overlay._run(["true"])

        environment = run.call_args.kwargs["env"]
        self.assertEqual("C", environment["LC_ALL"])
        self.assertEqual("UTC", environment["TZ"])

    def test_payload_copy_preserves_hardlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            overlay = root / "overlay"
            baseline.mkdir()
            first = baseline / "first.pyc"
            second = baseline / "second.pyc"
            first.write_bytes(b"bytecode")
            second.hardlink_to(first)

            rebuild_overlay._copytree_preserving_hardlinks(baseline, overlay)

            self.assertEqual(
                (overlay / "first.pyc").stat().st_ino,
                (overlay / "second.pyc").stat().st_ino,
            )

    def test_rejects_hardlink_topology_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            overlay = root / "overlay"
            baseline.mkdir()
            first = baseline / "first.pyc"
            second = baseline / "second.pyc"
            first.write_bytes(b"bytecode")
            second.hardlink_to(first)
            shutil.copytree(baseline, overlay)

            with self.assertRaisesRegex(
                rebuild_overlay.OverlayError, "changed payload hardlinks"
            ):
                rebuild_overlay._verify_hardlink_topology(baseline, overlay)

    def test_allows_only_the_exact_manifest_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            overlay = root / "overlay"
            baseline.mkdir()
            (baseline / "allowed.txt").write_text("vendor", encoding="utf-8")
            (baseline / "same.txt").write_text("same", encoding="utf-8")
            shutil.copytree(baseline, overlay)
            (overlay / "allowed.txt").write_text("overlay", encoding="utf-8")
            manifest = {
                "overlay": {
                    "modifiedFiles": [
                        {
                            "path": "allowed.txt",
                            "vendorSha256": sha256(baseline / "allowed.txt"),
                            "overlaySha256": sha256(overlay / "allowed.txt"),
                        }
                    ]
                }
            }

            rebuild_overlay.verify_tree(manifest, baseline, overlay)

            (overlay / "same.txt").write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(
                rebuild_overlay.OverlayError, "unexpected=.*same.txt"
            ):
                rebuild_overlay.verify_tree(manifest, baseline, overlay)

    def test_rejects_added_payload_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            overlay = root / "overlay"
            baseline.mkdir()
            (baseline / "allowed.txt").write_text("vendor", encoding="utf-8")
            shutil.copytree(baseline, overlay)
            (overlay / "added.txt").write_text("unexpected", encoding="utf-8")
            manifest = {
                "overlay": {
                    "modifiedFiles": [
                        {
                            "path": "allowed.txt",
                            "vendorSha256": sha256(baseline / "allowed.txt"),
                            "overlaySha256": "unused",
                        }
                    ]
                }
            }

            with self.assertRaisesRegex(
                rebuild_overlay.OverlayError, "added=.*added.txt"
            ):
                rebuild_overlay.verify_tree(manifest, baseline, overlay)

    def test_derived_bytecode_is_independent_of_build_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = "usr/lib64/python3.14/site-packages/example.py"
            output_path = (
                "usr/lib64/python3.14/site-packages/__pycache__/"
                f"example.{sys.implementation.cache_tag}.pyc"
            )
            manifest = {
                "overlay": {
                    "pythonCacheTag": sys.implementation.cache_tag,
                    "derivedBytecode": [
                        {
                            "source": source_path,
                            "path": output_path,
                            "optimization": 0,
                        }
                    ],
                }
            }
            builds = [root / "first", root / "second"]
            for build in builds:
                source = build / source_path
                source.parent.mkdir(parents=True)
                source.write_text("value = 42\n", encoding="utf-8")
                rebuild_overlay._compile_derived_bytecode(manifest, build)

            self.assertEqual(
                sha256(builds[0] / output_path), sha256(builds[1] / output_path)
            )

    def test_rejects_paths_outside_the_payload_root(self):
        with self.assertRaises(rebuild_overlay.OverlayError):
            rebuild_overlay._relative_path("../outside")
        with self.assertRaises(rebuild_overlay.OverlayError):
            rebuild_overlay._relative_path("/absolute")

    def test_patch_paths_are_absolute_before_payload_working_directory_changes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            source_directory = Path(directory)
            patch = source_directory / "change.patch"
            patch.write_text("test patch\n", encoding="utf-8")
            manifest = {
                "overlay": {
                    "patches": [
                        {
                            "file": patch.name,
                            "sha256": sha256(patch),
                        }
                    ]
                }
            }

            paths = rebuild_overlay._verify_patch_files(
                manifest, source_directory.relative_to(Path.cwd())
            )

            self.assertTrue(paths[0].is_absolute())
            self.assertEqual(paths[0], patch.resolve())


if __name__ == "__main__":
    unittest.main()
