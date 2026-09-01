# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "check-patch-whitespace.py"
SPEC = importlib.util.spec_from_file_location("check_patch_whitespace", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class PatchWhitespaceTests(unittest.TestCase):
    def test_rejects_trailing_whitespace_in_an_added_line(self):
        lines = [b"@@ -0,0 +1 @@", b"+value "]
        self.assertEqual([2], CHECKER.added_trailing_whitespace(lines))

    def test_checks_added_target_content_beginning_with_two_pluses(self):
        lines = [b"@@ -0,0 +1 @@", b"+++value "]
        self.assertEqual([2], CHECKER.added_trailing_whitespace(lines))

    def test_accepts_required_blank_context_marker(self):
        for marker in (b" ", b""):
            with self.subTest(marker=marker):
                lines = [b"@@ -1 +1 @@", marker]
                self.assertEqual([], CHECKER.added_trailing_whitespace(lines))

    def test_file_header_is_not_treated_as_target_content(self):
        lines = [
            b"--- a/example",
            b"+++ b/example ",
            b"@@ -0,0 +1 @@",
            b"+clean",
        ]
        self.assertEqual([], CHECKER.added_trailing_whitespace(lines))

    def test_rejects_bare_carriage_return_before_trailing_space(self):
        data = b"@@ -0,0 +1 @@\n+value\r \n"
        with self.assertRaisesRegex(ValueError, "Bare carriage return"):
            CHECKER.patch_lines(data)

    def test_accepts_crlf_framing(self):
        data = b"--- a/example\r\n+++ b/example\r\n@@ -0,0 +1 @@\r\n+value\r\n"
        lines = CHECKER.patch_lines(data)
        self.assertEqual([], CHECKER.added_trailing_whitespace(lines))


if __name__ == "__main__":
    unittest.main()
