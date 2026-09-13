# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from proton_vpn_kde_backend.capture_recovery import (
    PACKET_CAPTURE_RECOVERY_FILENAME,
    PacketCaptureRecoveryJournal,
)


class PacketCaptureRecoveryJournalTests(unittest.TestCase):
    def setUp(self):
        self._runtime_directory = tempfile.TemporaryDirectory()
        self.runtime_path = Path(self._runtime_directory.name)
        self.recovery_path = self.runtime_path / PACKET_CAPTURE_RECOVERY_FILENAME
        self.journal = PacketCaptureRecoveryJournal(self.recovery_path)

    def tearDown(self):
        self._runtime_directory.cleanup()

    def test_round_trip_is_private_atomic_and_clearable(self):
        self.assertFalse(self.journal.exists())
        self.journal.store_deadline(1234.5)

        self.assertTrue(self.journal.exists())
        self.assertEqual(1234.5, self.journal.load_deadline())
        self.assertEqual(0o600, stat.S_IMODE(self.recovery_path.stat().st_mode))
        self.assertEqual(
            [PACKET_CAPTURE_RECOVERY_FILENAME],
            sorted(path.name for path in self.runtime_path.iterdir()),
        )

        self.journal.clear()
        self.assertFalse(self.journal.exists())
        self.assertIsNone(self.journal.load_deadline())

    def test_invalid_or_permissive_record_is_rejected(self):
        self.recovery_path.write_text('{"version":1}', encoding="utf-8")
        self.assertTrue(self.journal.exists())
        with self.assertRaisesRegex(RuntimeError, "recovery state is invalid"):
            self.journal.load_deadline()

        self.recovery_path.write_text(
            '{"deadlineBootSeconds":1234.5,"version":1}', encoding="utf-8"
        )
        self.recovery_path.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "recovery state is invalid"):
            self.journal.load_deadline()

    def test_default_path_requires_private_runtime_directory(self):
        self.runtime_path.chmod(0o755)
        with patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": str(self.runtime_path)}, clear=False
        ):
            with self.assertRaisesRegex(RuntimeError, "is not private"):
                PacketCaptureRecoveryJournal()


if __name__ == "__main__":
    unittest.main()
