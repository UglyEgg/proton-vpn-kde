# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Backend service entry point."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Coroutine
import logging
import os
import signal as unix_signal
from typing import Any

from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, NameFlag, RequestNameReply

from .adapters import DemoCoreAdapter, ProtonCoreAdapter
from .client_authorization import ClientAuthorizer
from .controller import BackendController
from .dbus_contract import BUS_NAME, OBJECT_PATH
from .dbus_service import VpnDbusService
from .features import TRUSTED_CLIENT_EXECUTABLES
from .lifetime import BackendLifetime, name_has_owner


DEFAULT_IDLE_TIMEOUT_SECONDS = 10.0
PROCESS_TASK_SHUTDOWN_SECONDS = 1.0
logger = logging.getLogger(__name__)


def _seconds_from_environment(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, default)))
    except ValueError:
        return default


def _idle_timeout_seconds(demo: bool) -> float:
    """Allow short test/demo lifetimes without trusting production environment."""
    if not demo:
        return DEFAULT_IDLE_TIMEOUT_SECONDS
    return _seconds_from_environment(
        "PROTON_VPN_KDE_IDLE_TIMEOUT_SECONDS", DEFAULT_IDLE_TIMEOUT_SECONDS
    )


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
    adapter = (
        DemoCoreAdapter(logged_in=not demo_logged_out) if demo else ProtonCoreAdapter()
    )
    controller = BackendController(adapter)

    stopped = asyncio.Event()
    lifetime = BackendLifetime(
        controller,
        stopped,
        lambda name: name_has_owner(bus, name),
        idle_timeout=_idle_timeout_seconds(demo),
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
    # Publish the well-known name only after the authorization ingress and
    # exported object are ready. Frontends react to NameOwnerChanged
    # immediately and must never observe a half-published service.
    reply = await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
    if not _owns_bus_name(reply):
        bus.unexport(OBJECT_PATH, service)
        bus.remove_message_handler(authorizer.message_handler)
        await authorizer.uninstall()
        bus.disconnect()
        return 0

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
        # Stop accepting new D-Bus work before draining the current serialized
        # mutation. This keeps package upgrades and session shutdown from
        # cancelling a logout after it has persisted protection changes.
        bus.unexport(OBJECT_PATH, service)
        bus.remove_message_handler(authorizer.message_handler)
        try:
            if initialized:
                await controller.close()
        finally:
            try:
                await authorizer.uninstall()
            finally:
                await bus.release_name(BUS_NAME)
                bus.disconnect()


async def _retire_process_tasks(timeout: float) -> set[asyncio.Task[Any]]:
    """Bound loop retirement after public service ownership is released."""
    current = asyncio.current_task()
    pending = {
        task
        for task in asyncio.all_tasks()
        if task is not current and not task.done()
    }
    for task in pending:
        task.cancel()
    if not pending:
        return set()
    done, still_pending = await asyncio.wait(pending, timeout=timeout)
    for task in done:
        try:
            task.result()
        except (Exception, asyncio.CancelledError):
            pass
    return still_pending


def _run_service(coroutine: Coroutine[Any, Any, int]) -> int:
    """Run the service with a finite final task-retirement budget."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    abandoned_task_ids: set[int] = set()

    def report_loop_error(
        reporting_loop: asyncio.AbstractEventLoop,
        context: dict[str, Any],
    ) -> None:
        task = context.get("task")
        if (
            context.get("message") == "Task was destroyed but it is pending!"
            and task is not None
            and id(task) in abandoned_task_ids
        ):
            return
        reporting_loop.default_exception_handler(context)

    loop.set_exception_handler(report_loop_error)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        try:
            abandoned = loop.run_until_complete(
                _retire_process_tasks(PROCESS_TASK_SHUTDOWN_SECONDS)
            )
            abandoned_task_ids.update(map(id, abandoned))
            if abandoned:
                logger.error(
                    "Process exit abandoned %d cancellation-resistant cleanup task(s)",
                    len(abandoned),
                )
        finally:
            asyncio.set_event_loop(None)
            loop.close()


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
    exit_code = _run_service(
        run(
            demo=args.demo or args.demo_logged_out, demo_logged_out=args.demo_logged_out
        )
    )
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
