from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from proton_vpn_kde_backend.support import collect_support_logs


class SupportLogTests(unittest.TestCase):
    def test_collects_only_nonempty_successful_fixed_journals(self):
        calls = 0

        def run(command, *, stdout, stderr, check, timeout):
            nonlocal calls
            calls += 1
            self.assertEqual("journalctl", command[0])
            self.assertIn("--since=-1d", command)
            self.assertIs(stderr, subprocess.DEVNULL)
            self.assertFalse(check)
            self.assertEqual(20, timeout)
            if calls == 1:
                stdout.write(b"backend diagnostic\n")
                return subprocess.CompletedProcess(command, 0)
            if calls == 2:
                stdout.write(b"ignored failure\n")
                return subprocess.CompletedProcess(command, 1)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as directory:
            with patch("proton_vpn_kde_backend.support.subprocess.run", run):
                paths = collect_support_logs(Path(directory))

            self.assertEqual(["ProtonVPNKDE.log"], [path.name for path in paths])
            self.assertEqual(b"backend diagnostic\n", paths[0].read_bytes())
            self.assertFalse((Path(directory) / "NetworkManager.log").exists())
            self.assertFalse((Path(directory) / "SplitTunneling.log").exists())


if __name__ == "__main__":
    unittest.main()
