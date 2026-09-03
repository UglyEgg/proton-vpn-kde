# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
from collections.abc import Callable
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from dbus_fast.constants import RequestNameReply

from proton_vpn_kde_backend import __main__ as backend_main
from proton_vpn_kde_backend.capture_recovery import PacketCaptureRecoveryJournal
from proton_vpn_kde_backend.controller import VpnSnapshot


class BackendMainTests(unittest.TestCase):
    def test_production_ignores_idle_timeout_environment_override(self):
        with patch.dict(
            os.environ,
            {"PROTON_VPN_KDE_IDLE_TIMEOUT_SECONDS": "inf"},
        ):
            self.assertEqual(
                backend_main.DEFAULT_IDLE_TIMEOUT_SECONDS,
                backend_main._idle_timeout_seconds(False),
            )

    def test_demo_accepts_test_idle_timeout(self):
        with patch.dict(
            os.environ,
            {"PROTON_VPN_KDE_IDLE_TIMEOUT_SECONDS": "2"},
        ):
            self.assertEqual(2.0, backend_main._idle_timeout_seconds(True))

    def test_process_runner_bounds_cancellation_resistant_cleanup(self):
        async def cancellation_resistant_cleanup():
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                await asyncio.Future()

        async def service():
            asyncio.create_task(cancellation_resistant_cleanup())
            await asyncio.sleep(0)
            return 7

        started = time.monotonic()
        with (
            patch.object(
                backend_main, "PROCESS_TASK_SHUTDOWN_SECONDS", 0.01
            ),
            self.assertLogs(
                "proton_vpn_kde_backend.__main__", level="ERROR"
            ) as captured,
        ):
            result = backend_main._run_service(service())

        self.assertEqual(7, result)
        self.assertLess(time.monotonic() - started, 0.1)
        self.assertIn("cancellation-resistant", "\n".join(captured.output))


class BackendPublicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_is_ready_before_well_known_name_is_published(self):
        events: list[str] = []

        class FakeBus:
            async def connect(self):
                events.append("connect")
                return self

            async def request_name(self, *_args):
                events.append("request-name")
                return RequestNameReply.PRIMARY_OWNER

            def add_message_handler(self, _handler):
                events.append("add-handler")

            def remove_message_handler(self, _handler):
                events.append("remove-handler")

            def export(self, _path, _service):
                events.append("export")

            def unexport(self, _path, _service):
                events.append("unexport")

            async def release_name(self, _name):
                events.append("release-name")

            def disconnect(self):
                events.append("disconnect")

        class FakeController:
            async def start(self):
                events.append("start")
                return False

        class FakeLifetime:
            async def run(self):
                await backend_main.asyncio.Event().wait()

        class FakeAuthorizer:
            message_handler = object()

            async def install(self):
                events.append("install-authorizer")

            async def uninstall(self):
                events.append("uninstall-authorizer")

        bus = FakeBus()
        with (
            patch.object(backend_main, "MessageBus", return_value=bus),
            patch.object(backend_main, "DemoCoreAdapter", return_value=object()),
            patch.object(
                backend_main,
                "BackendController",
                return_value=FakeController(),
            ),
            patch.object(
                backend_main,
                "BackendLifetime",
                return_value=FakeLifetime(),
            ),
            patch.object(
                backend_main,
                "ClientAuthorizer",
                return_value=FakeAuthorizer(),
            ),
            patch.object(backend_main, "VpnDbusService", return_value=object()),
        ):
            self.assertEqual(1, await backend_main.run(demo=True))

        publication = events.index("request-name")
        self.assertLess(events.index("install-authorizer"), publication)
        self.assertLess(events.index("add-handler"), publication)
        self.assertLess(events.index("export"), publication)

    async def test_capture_recovery_cannot_be_cancelled_by_idle_startup(self):
        start_entered = asyncio.Event()
        release_start = asyncio.Event()
        start_cancelled = asyncio.Event()

        class FakeBus:
            async def connect(self):
                return self

            async def request_name(self, *_args):
                return RequestNameReply.PRIMARY_OWNER

            def add_message_handler(self, _handler):
                pass

            def remove_message_handler(self, _handler):
                pass

            def export(self, _path, _service):
                pass

            def unexport(self, _path, _service):
                pass

            async def release_name(self, _name):
                pass

            def disconnect(self):
                pass

        class FakeAuthorizer:
            message_handler = object()

            async def install(self):
                pass

            async def uninstall(self):
                pass

        with tempfile.TemporaryDirectory() as runtime_directory:
            runtime_path = Path(runtime_directory)
            runtime_path.chmod(0o700)
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime_directory}):
                journal = PacketCaptureRecoveryJournal()
                journal.store_deadline(100.0)

                class FakeController:
                    def __init__(self):
                        self.snapshot = VpnSnapshot()
                        self._listeners: list[
                            Callable[[VpnSnapshot], None]
                        ] = []

                    def subscribe(self, callback):
                        self._listeners.append(callback)

                    def has_pending_startup_recovery(self):
                        return journal.exists()

                    async def start(self):
                        start_entered.set()
                        try:
                            await release_start.wait()
                        except asyncio.CancelledError:
                            start_cancelled.set()
                            raise
                        journal.clear()
                        self.snapshot = VpnSnapshot(
                            ready=True,
                            state="disconnected",
                        )
                        for callback in self._listeners:
                            callback(self.snapshot)
                        return True

                    async def close(self):
                        pass

                controller = FakeController()
                with (
                    patch.object(
                        backend_main, "MessageBus", return_value=FakeBus()
                    ),
                    patch.object(
                        backend_main, "DemoCoreAdapter", return_value=object()
                    ),
                    patch.object(
                        backend_main,
                        "BackendController",
                        return_value=controller,
                    ),
                    patch.object(
                        backend_main,
                        "ClientAuthorizer",
                        return_value=FakeAuthorizer(),
                    ),
                    patch.object(
                        backend_main, "VpnDbusService", return_value=object()
                    ),
                    patch.object(
                        backend_main, "_idle_timeout_seconds", return_value=0.01
                    ),
                ):
                    run_task = asyncio.create_task(backend_main.run(demo=True))
                    await asyncio.wait_for(start_entered.wait(), timeout=0.2)
                    await asyncio.sleep(0.04)
                    self.assertFalse(run_task.done())
                    self.assertFalse(start_cancelled.is_set())
                    release_start.set()
                    self.assertEqual(
                        0,
                        await asyncio.wait_for(run_task, timeout=0.2),
                    )

                self.assertFalse(journal.exists())
                self.assertFalse(start_cancelled.is_set())


if __name__ == "__main__":
    unittest.main()
