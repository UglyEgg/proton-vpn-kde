"""Headless backend for the native Proton VPN KDE frontend."""

from .controller import BackendController, VpnSnapshot

__version__ = "0.11.2"

__all__ = ["BackendController", "VpnSnapshot", "__version__"]
