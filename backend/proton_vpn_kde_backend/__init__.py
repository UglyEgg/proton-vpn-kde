# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Headless backend for the native Proton VPN KDE frontend."""

from .controller import BackendController, VpnSnapshot

__version__ = "0.11.3"

__all__ = ["BackendController", "VpnSnapshot", "__version__"]
