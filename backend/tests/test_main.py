# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from dbus_fast.constants import RequestNameReply

from proton_vpn_kde_backend import __main__ as backend_main


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


if __name__ == "__main__":
    unittest.main()
