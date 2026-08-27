"""Backend service entry point."""

from __future__ import annotations

import argparse
import asyncio
import signal as unix_signal

from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType

from .adapters import DemoCoreAdapter, ProtonCoreAdapter
from .controller import BackendController
from .dbus_service import BUS_NAME, OBJECT_PATH, VpnDbusService


async def run(demo: bool, demo_logged_out: bool = False) -> None:
    adapter = (
        DemoCoreAdapter(logged_in=not demo_logged_out) if demo else ProtonCoreAdapter()
    )
    controller = BackendController(adapter)

    bus = await MessageBus(
        bus_type=BusType.SESSION,
        negotiate_unix_fd=True,
    ).connect()
    service = VpnDbusService(controller)
    bus.export(OBJECT_PATH, service)
    await bus.request_name(BUS_NAME)

    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (unix_signal.SIGINT, unix_signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)

    await controller.start()

    try:
        await stopped.wait()
    finally:
        await controller.close()
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
    asyncio.run(
        run(
            demo=args.demo or args.demo_logged_out, demo_logged_out=args.demo_logged_out
        )
    )


if __name__ == "__main__":
    main()
