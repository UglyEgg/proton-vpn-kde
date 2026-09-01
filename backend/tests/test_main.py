# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from proton_vpn_kde_backend.__main__ import (
    DEFAULT_IDLE_TIMEOUT_SECONDS,
    _idle_timeout_seconds,
)


class BackendMainTests(unittest.TestCase):
    def test_production_ignores_idle_timeout_environment_override(self):
        with patch.dict(
            os.environ,
            {"PROTON_VPN_KDE_IDLE_TIMEOUT_SECONDS": "inf"},
        ):
            self.assertEqual(DEFAULT_IDLE_TIMEOUT_SECONDS, _idle_timeout_seconds(False))

    def test_demo_accepts_test_idle_timeout(self):
        with patch.dict(
            os.environ,
            {"PROTON_VPN_KDE_IDLE_TIMEOUT_SECONDS": "2"},
        ):
            self.assertEqual(2.0, _idle_timeout_seconds(True))


if __name__ == "__main__":
    unittest.main()
