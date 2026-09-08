# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Backend service entry point."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Coroutine
import logging
import os
import signal as unix_signal
import threading
import time
from typing import Any, NoReturn

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
RUN_SHUTDOWN_SECONDS = 30.0
TASK_CANCELLATION_GRACE_SECONDS = 0.25
PROCESS_TASK_SHUTDOWN_SECONDS = 1.0
PROCESS_THREAD_SHUTDOWN_SECONDS = 0.25
INCOMPLETE_SHUTDOWN_EXIT_CODE = 1
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


async def _finish_task_before_deadline(
    task: asyncio.Task[Any],
    deadline: float,
    *,
    cancel: bool = False,
    grace_seconds: float | None = None,
) -> BaseException | None:
    """Join one owned task without allowing cleanup to outlive a deadline."""
    if cancel and not task.done() and not task.cancelling():
        task.cancel()
    if not task.done():
        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        if grace_seconds is not None:
            remaining = min(remaining, max(0.0, grace_seconds))
        if remaining:
            done, _ = await asyncio.wait({task}, timeout=remaining)
            if task not in done:
                return TimeoutError("Backend cleanup exceeded its shutdown deadline")
        else:
            return TimeoutError("Backend cleanup exceeded its shutdown deadline")
    try:
        task.result()
    except asyncio.CancelledError as error:
        return None if cancel else error
    except BaseException as error:
        return error
    return None


async def _run_cleanup_before_deadline(
    operation: Coroutine[Any, Any, Any],
    deadline: float,
) -> BaseException | None:
    """Start and bound one cleanup operation under the run-level deadline."""
    if asyncio.get_running_loop().time() >= deadline:
        operation.close()
        return TimeoutError("Backend cleanup exceeded its shutdown deadline")
    task = asyncio.create_task(operation)
    error = await _finish_task_before_deadline(task, deadline)
    if isinstance(error, TimeoutError) and not task.done():
        task.cancel()
    return error


async def _shutdown_published_service(
    *,
    bus: Any,
    service: Any,
    authorizer: ClientAuthorizer,
    controller: BackendController,
    initialized: bool,
    initialization_task: asyncio.Task[Any] | None,
    lifetime_task: asyncio.Task[Any] | None,
    stopped_task: asyncio.Task[Any] | None,
    loop: asyncio.AbstractEventLoop,
) -> BaseException | None:
    """Close public ingress and all owned work under one absolute deadline."""
    shutdown_deadline = loop.time() + RUN_SHUTDOWN_SECONDS
    cleanup_error: BaseException | None = None
    try:
        # Close public ingress synchronously before waiting for any accepted
        # startup, lifetime, or controller work.
        authorizer.close_ingress()
        try:
            bus.unexport(OBJECT_PATH, service)
        except BaseException as error:
            cleanup_error = error
        for task in (initialization_task, lifetime_task, stopped_task):
            if task is None:
                continue
            task_error = await _finish_task_before_deadline(
                task,
                shutdown_deadline,
                cancel=True,
                grace_seconds=TASK_CANCELLATION_GRACE_SECONDS,
            )
            if task_error is not None and cleanup_error is None:
                cleanup_error = task_error
        if initialized:
            controller_error = await _run_cleanup_before_deadline(
                controller.close(deadline=shutdown_deadline), shutdown_deadline
            )
            if controller_error is not None and cleanup_error is None:
                cleanup_error = controller_error
        authorizer_error = await _run_cleanup_before_deadline(
            authorizer.uninstall(), shutdown_deadline
        )
        if authorizer_error is not None and cleanup_error is None:
            cleanup_error = authorizer_error
        release_error = await _run_cleanup_before_deadline(
            bus.release_name(BUS_NAME), shutdown_deadline
        )
        if release_error is not None and cleanup_error is None:
            cleanup_error = release_error
    finally:
        try:
            # Synchronous disconnect is the authoritative name-drop fallback
            # even when a D-Bus cleanup call suppresses cancellation, raises,
            # or consumes the shared deadline.
            bus.disconnect()
        except BaseException as error:
            if cleanup_error is None:
                cleanup_error = error
        for sig in (unix_signal.SIGINT, unix_signal.SIGTERM):
            try:
                loop.remove_signal_handler(sig)
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
    return cleanup_error


async def _shutdown_unowned_publication(
    bus: Any,
    service: Any,
    authorizer: ClientAuthorizer,
) -> BaseException | None:
    """Undo a refused publication and always close its bus connection."""
    cleanup_error: BaseException | None = None
    try:
        authorizer.close_ingress()
        try:
            bus.unexport(OBJECT_PATH, service)
        except BaseException as error:
            cleanup_error = error
        deadline = asyncio.get_running_loop().time() + RUN_SHUTDOWN_SECONDS
        authorizer_error = await _run_cleanup_before_deadline(
            authorizer.uninstall(), deadline
        )
        if authorizer_error is not None and cleanup_error is None:
            cleanup_error = authorizer_error
    finally:
        try:
            bus.disconnect()
        except BaseException as error:
            if cleanup_error is None:
                cleanup_error = error
    return cleanup_error


async def run(demo: bool, demo_logged_out: bool = False) -> int:
    bus = MessageBus(
        bus_type=BusType.SESSION,
        negotiate_unix_fd=True,
    )
    authorizer = ClientAuthorizer(
        bus,
        TRUSTED_CLIENT_EXECUTABLES,
        enforce_identity=not demo,
    )
    authorizer.close_ingress()
    bus.add_message_handler(authorizer.message_handler)
    try:
        await bus.connect()
    except BaseException:
        bus.disconnect()
        raise
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
    service = VpnDbusService(controller, lifetime, authorizer)
    try:
        await authorizer.install()
        bus.export(OBJECT_PATH, service)
        authorizer.open_ingress()
        # Publish the well-known name only after the authorization ingress and
        # exported object are ready. Frontends react to NameOwnerChanged
        # immediately and must never observe a half-published service.
        reply = await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
    except BaseException:
        setup_cleanup_error = await _shutdown_unowned_publication(
            bus, service, authorizer
        )
        if setup_cleanup_error is not None:
            logger.error(
                "Backend publication rollback was incomplete (%s)",
                type(setup_cleanup_error).__name__,
            )
        raise
    if not _owns_bus_name(reply):
        refusal_cleanup_error = await _shutdown_unowned_publication(
            bus, service, authorizer
        )
        if refusal_cleanup_error is not None:
            raise refusal_cleanup_error
        return 0

    loop = asyncio.get_running_loop()
    try:
        for sig in (unix_signal.SIGINT, unix_signal.SIGTERM):
            loop.add_signal_handler(sig, stopped.set)
    except BaseException:
        signal_cleanup_error = await _shutdown_published_service(
            bus=bus,
            service=service,
            authorizer=authorizer,
            controller=controller,
            initialized=False,
            initialization_task=None,
            lifetime_task=None,
            stopped_task=None,
            loop=loop,
        )
        if signal_cleanup_error is not None:
            logger.error(
                "Backend signal setup rollback was incomplete (%s)",
                type(signal_cleanup_error).__name__,
            )
        raise

    lifetime_task: asyncio.Task | None = None
    initialization_task: asyncio.Task | None = None
    stopped_task: asyncio.Task | None = None
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
            return 0
        stopped_task.cancel()
        initialized = bool(initialization_task.result())
        if not initialized:
            # A non-zero process exit lets systemd's Restart=on-failure policy
            # recover from transient Secret Service, Proton Core, or
            # NetworkManager initialization failures.
            return 1
        await stopped.wait()
        return 0
    finally:
        cleanup_error = await _shutdown_published_service(
            bus=bus,
            service=service,
            authorizer=authorizer,
            controller=controller,
            initialized=initialized,
            initialization_task=initialization_task,
            lifetime_task=lifetime_task,
            stopped_task=stopped_task,
            loop=loop,
        )
        if cleanup_error is not None:
            raise cleanup_error


async def _retire_process_tasks(timeout: float) -> set[asyncio.Task[Any]]:
    """Reach a bounded fixed point after public service ownership is released."""
    current = asyncio.current_task()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, timeout)
    quiescent_passes = 0
    while True:
        # Let cancellation handlers and done callbacks publish their children
        # before taking the next ownership snapshot.
        await asyncio.sleep(0)
        pending = {
            task
            for task in asyncio.all_tasks()
            if task is not current and not task.done()
        }
        if not pending:
            quiescent_passes += 1
            if quiescent_passes >= 2:
                return set()
            continue
        quiescent_passes = 0
        for task in pending:
            task.cancel()
        remaining = deadline - loop.time()
        if remaining <= 0:
            return pending
        done, still_pending = await asyncio.wait(pending, timeout=remaining)
        for task in done:
            try:
                task.result()
            except (Exception, asyncio.CancelledError):
                pass
        if still_pending and loop.time() >= deadline:
            return {
                task
                for task in asyncio.all_tasks()
                if task is not current and not task.done()
            }


def _new_non_daemon_threads(
    baseline: frozenset[threading.Thread],
) -> list[threading.Thread]:
    current = threading.current_thread()
    return [
        thread
        for thread in threading.enumerate()
        if thread is not current
        and thread not in baseline
        and thread.is_alive()
        and not thread.daemon
    ]


def _retire_process_threads(
    baseline: frozenset[threading.Thread], timeout: float
) -> list[threading.Thread]:
    """Join service-created process owners to a finite fixed point."""
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        pending = _new_non_daemon_threads(baseline)
        if not pending:
            return []
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return pending
        for thread in pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            thread.join(remaining)


def _run_service(
    coroutine: Coroutine[Any, Any, int],
    *,
    terminal_exit: Callable[[int], NoReturn] = os._exit,
) -> int:
    """Run the service with finite task and process-owner retirement."""
    baseline_threads = frozenset(threading.enumerate())
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
            try:
                loop.close()
            finally:
                lingering_threads = _retire_process_threads(
                    baseline_threads, PROCESS_THREAD_SHUTDOWN_SECONDS
                )
                if lingering_threads:
                    logger.critical(
                        "Process exit forced with %d non-daemon service thread(s) "
                        "still running: %s",
                        len(lingering_threads),
                        ", ".join(
                            sorted({thread.name for thread in lingering_threads})
                        ),
                    )
                    terminal_exit(INCOMPLETE_SHUTDOWN_EXIT_CODE)


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
