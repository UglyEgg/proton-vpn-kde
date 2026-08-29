"""Headless backend for the native Proton VPN KDE frontend."""

from .controller import BackendController, VpnSnapshot

__version__ = "0.8.8"

__all__ = ["BackendController", "VpnSnapshot", "__version__"]
