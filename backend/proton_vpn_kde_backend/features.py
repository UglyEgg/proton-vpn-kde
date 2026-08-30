# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Conservative feature defaults for source-tree and packaged execution."""

try:
    from ._build_features import (
        CRASH_REPORT_SUBMISSION_ENABLED,
        SUPPORT_REPORT_SUBMISSION_ENABLED,
        TRUSTED_CLIENT_EXECUTABLES,
    )
except ImportError:
    CRASH_REPORT_SUBMISSION_ENABLED = False
    SUPPORT_REPORT_SUBMISSION_ENABLED = False
    TRUSTED_CLIENT_EXECUTABLES = (
        "/usr/bin/proton-vpn-kde",
        "/usr/bin/proton-vpn-kde-agent",
    )

__all__ = [
    "CRASH_REPORT_SUBMISSION_ENABLED",
    "SUPPORT_REPORT_SUBMISSION_ENABLED",
    "TRUSTED_CLIENT_EXECUTABLES",
]
