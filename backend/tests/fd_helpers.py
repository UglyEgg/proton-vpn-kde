# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Portable file-descriptor creation for backend unit tests."""

from __future__ import annotations

import os
from tempfile import TemporaryFile


def create_test_fd(name: str) -> int:
    memfd_create = getattr(os, "memfd_create", None)
    if callable(memfd_create):
        return memfd_create(name, getattr(os, "MFD_CLOEXEC", 0))
    with TemporaryFile(prefix=f"{name}-") as temporary:
        return os.dup(temporary.fileno())
