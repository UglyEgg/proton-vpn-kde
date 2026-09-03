# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Runtime compatibility probes for the installed Proton Core package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any


FIDO2_CANCELLABLE_SELECTION_CAPABILITY = (
    "supports_cancellable_fido2_key_selection"
)


def cancellable_fido2_available(api: Any) -> bool:
    """Require Core to guarantee cancellation through key selection.

    Current Core releases expose an assertion cancellation event but do not
    use it while selecting among multiple attached keys.  The GUI must not
    advertise a flow it cannot cancel and join safely.  A future Core can opt
    in with an explicit capability once the complete selection path observes
    the public cancellation event.
    """

    return bool(
        getattr(api, "supports_fido2", False)
        and getattr(api, FIDO2_CANCELLABLE_SELECTION_CAPABILITY, False)
    )


def core_memory_optimization_behavior(logicals_module: Any) -> bool:
    """Check both supported string-sharing paths without touching live Core state."""
    deduplicate = getattr(logicals_module, "_deduplicate_server_strings", None)
    hook_factory = getattr(logicals_module, "_server_string_object_hook", None)
    if not callable(deduplicate) or not callable(hook_factory):
        return False

    first = bytes("phase8-runtime-probe.example", "utf-8").decode("utf-8")
    second = bytes("phase8-runtime-probe.example", "utf-8").decode("utf-8")
    if first is second:
        return False
    decoded: list[dict[str, Any]] = [
        {"Domain": first, "Servers": [{"Domain": second}]}
    ]
    try:
        deduplicate(decoded)
    except Exception:
        return False
    if decoded[0]["Domain"] is not decoded[0]["Servers"][0]["Domain"]:
        return False

    third = bytes("phase8-cache-probe.example", "utf-8").decode("utf-8")
    fourth = bytes("phase8-cache-probe.example", "utf-8").decode("utf-8")
    if third is fourth:
        return False
    try:
        object_hook = hook_factory()
        first_item = object_hook({"Domain": third})
        second_item = object_hook({"Domain": fourth})
    except Exception:
        return False
    return first_item["Domain"] is second_item["Domain"]


def core_memory_optimizations_active() -> bool:
    try:
        from proton.vpn.session.servers import logicals
    except (ImportError, ModuleNotFoundError):
        return False
    return core_memory_optimization_behavior(logicals)


def core_package_version() -> str:
    try:
        return version("proton-vpn-api-core")
    except PackageNotFoundError:
        return ""
