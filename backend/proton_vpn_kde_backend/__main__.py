"""Backend service entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
import signal as unix_signal

from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, NameFlag, RequestNameReply

from .adapters import DemoCoreAdapter, ProtonCoreAdapter
from .client_authorization import ClientAuthorizer
from .controller import BackendController
from .dbus_service import BUS_NAME, OBJECT_PATH, VpnDbusService
from .features import TRUSTED_CLIENT_EXECUTABLES
from .lifetime import BackendLifetime, name_has_owner


def _seconds_from_environment(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, default)))
    except ValueError:
        return default


def _owns_bus_name(reply: RequestNameReply) -> bool:
    return reply in {
        RequestNameReply.PRIMARY_OWNER,
        RequestNameReply.ALREADY_OWNER,
    }


async def run(demo: bool, demo_logged_out: bool = False) -> int:
    bus = await MessageBus(
        bus_type=BusType.SESSION,
        negotiate_unix_fd=True,
    ).connect()
    reply = await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
    if not _owns_bus_name(reply):
        bus.disconnect()
        return 0

    adapter = (
        DemoCoreAdapter(logged_in=not demo_logged_out) if demo else ProtonCoreAdapter()
    )
    controller = BackendController(adapter)

    stopped = asyncio.Event()
    lifetime = BackendLifetime(
        controller,
        stopped,
        lambda name: name_has_owner(bus, name),
        idle_timeout=_seconds_from_environment(
            "PROTON_VPN_KDE_IDLE_TIMEOUT_SECONDS", 10.0
        ),
        poll_interval=_seconds_from_environment(
            "PROTON_VPN_KDE_CLIENT_POLL_SECONDS", 2.0
        ),
    )
    authorizer = ClientAuthorizer(
        bus,
        TRUSTED_CLIENT_EXECUTABLES,
        enforce_identity=not demo,
    )
    await authorizer.install()
    bus.add_message_handler(authorizer.message_handler)
    service = VpnDbusService(controller, lifetime, authorizer)
    bus.export(OBJECT_PATH, service)

    loop = asyncio.get_running_loop()
    for sig in (unix_signal.SIGINT, unix_signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)

    lifetime_task: asyncio.Task | None = None
    initialization_task: asyncio.Task | None = None
    initialized = False

    try:
        lifetime_task = asyncio.create_task(lifetime.run())
        initialization_task = asyncio.create_task(controller.start())
        stopped_task = asyncio.create_task(stopped.wait())
        done, _ = await asyncio.wait(
            {initialization_task, stopped_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if stopped_task in done and initialization_task not in done:
            initialization_task.cancel()
            await asyncio.gather(initialization_task, return_exceptions=True)
            return 0
        stopped_task.cancel()
        await asyncio.gather(stopped_task, return_exceptions=True)
        initialized = bool(initialization_task.result())
        if not initialized:
            # A non-zero process exit lets systemd's Restart=on-failure policy
            # recover from transient Secret Service, Proton Core, or
            # NetworkManager initialization failures.
            return 1
        await stopped.wait()
        return 0
    finally:
        if initialization_task is not None and not initialization_task.done():
            initialization_task.cancel()
            await asyncio.gather(initialization_task, return_exceptions=True)
        if lifetime_task is not None:
            lifetime_task.cancel()
            await asyncio.gather(lifetime_task, return_exceptions=True)
        if initialized:
            await controller.close()
        bus.unexport(OBJECT_PATH, service)
        bus.remove_message_handler(authorizer.message_handler)
        await authorizer.uninstall()
        await bus.release_name(BUS_NAME)
        bus.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Headless Proton VPN service for the native KDE frontend"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="run without touching Proton credentials, networking, or NetworkManager",
    )
    parser.add_argument(
        "--demo-logged-out",
        action="store_true",
        help="show the safe demo authentication UI without using a Proton account",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(
        run(
            demo=args.demo or args.demo_logged_out, demo_logged_out=args.demo_logged_out
        )
    )
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
