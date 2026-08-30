# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
from time import monotonic
import unittest

from proton_vpn_kde_backend.support import (
    TRUNCATION_MARKER,
    _JOURNAL_SOURCES,
    collect_support_logs,
)


def python_source(filename: str, program: str) -> tuple[str, tuple[str, ...]]:
    return filename, (sys.executable, "-c", program)


class SupportLogTests(unittest.TestCase):
    def test_production_sources_are_fixed_to_one_day_and_known_units(self):
        self.assertEqual(3, len(_JOURNAL_SOURCES))
        for _filename, command in _JOURNAL_SOURCES:
            self.assertEqual("journalctl", command[0])
            self.assertIn("--since=-1d", command)
            self.assertIn("--no-pager", command)

    def test_collects_only_nonempty_successful_sources(self):
        sources = (
            python_source("kept.log", "print('backend diagnostic')"),
            python_source("failed.log", "print('ignored'); raise SystemExit(1)"),
            python_source("empty.log", "pass"),
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = collect_support_logs(Path(directory), sources=sources)

            self.assertEqual(["kept.log"], [path.name for path in paths])
            self.assertEqual(b"backend diagnostic\n", paths[0].read_bytes())
            self.assertFalse((Path(directory) / "failed.log").exists())
            self.assertFalse((Path(directory) / "empty.log").exists())

    def test_truncates_while_streaming_at_per_source_limit(self):
        sources = (
            python_source(
                "large.log",
                "import os; os.write(1, b'x' * 1048576)",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = collect_support_logs(
                Path(directory),
                sources=sources,
                per_source_limit=256,
                aggregate_limit=1024,
            )

            self.assertEqual(1, len(paths))
            self.assertEqual(256, paths[0].stat().st_size)
            self.assertTrue(paths[0].read_bytes().endswith(TRUNCATION_MARKER))

    def test_aggregate_limit_bounds_all_retained_files(self):
        sources = tuple(
            python_source(f"{index}.log", "import os; os.write(1, b'x' * 100)")
            for index in range(3)
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = collect_support_logs(
                Path(directory),
                sources=sources,
                per_source_limit=128,
                aggregate_limit=150,
            )

            self.assertLessEqual(sum(path.stat().st_size for path in paths), 150)

    def test_timeout_terminates_and_discards_partial_output(self):
        sources = (
            python_source(
                "slow.log",
                "import time; print('partial', flush=True); time.sleep(5)",
            ),
        )
        started = monotonic()
        with tempfile.TemporaryDirectory() as directory:
            paths = collect_support_logs(
                Path(directory), sources=sources, timeout_seconds=0.05
            )

            self.assertEqual([], paths)
            self.assertFalse((Path(directory) / "slow.log").exists())
        self.assertLess(monotonic() - started, 2.0)


if __name__ == "__main__":
    unittest.main()
