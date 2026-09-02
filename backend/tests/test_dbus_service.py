# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, Mock

from dbus_fast.errors import DBusError

from fd_helpers import create_test_fd
from proton_vpn_kde_backend.adapters import DemoCoreAdapter
from proton_vpn_kde_backend.controller import BackendController
from proton_vpn_kde_backend.dbus_service import (
    INVALID_SUPPORT_REPORT_ERROR,
    INVALID_SETTINGS_ERROR,
    NPS_COMPLETION_UNKNOWN_ERROR,
    OPERATION_FAILED_ERROR,
    OPERATION_FAILED_MESSAGE,
    SUPPORT_REPORT_DISABLED_MESSAGE,
    VpnDbusService,
)
from proton_vpn_kde_backend.errors import (
    NpsCompletionUnknownError,
    UserVisibleValueError,
)


SENTINEL = "credential=must-not-cross-dbus /workspace/private.py"


def make_service() -> tuple[VpnDbusService, Mock]:
    controller = Mock()
    controller.connect_country = AsyncMock()
    controller.connect_fastest_with_feature = AsyncMock()
    controller.connect_fastest_with_features = AsyncMock()
    controller.connect_country_with_features = AsyncMock()
    controller.connect_group_with_features = AsyncMock()
    controller.update_settings_json = AsyncMock()
    service = VpnDbusService(controller)
    return service, controller


class VpnDbusServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_authorizer_revocation_releases_lifetime_lease(self):
        controller = Mock()
        lifetime = Mock()
        authorizer = Mock()

        VpnDbusService(controller, lifetime, authorizer)

        authorizer.subscribe_revocation.assert_any_call(
            lifetime.unregister_client
        )

    async def test_registration_rolls_back_owner_loss_after_authorization(self):
        controller = Mock()
        lifetime = Mock()
        authorizer = Mock()
        authorizer.authorize = AsyncMock()
        authorizer.require_authorized_sender.side_effect = PermissionError
        service = VpnDbusService(controller, lifetime, authorizer)

        with self.assertRaises(DBusError):
            await type(service).register_client.__wrapped__(service, ":direct.test")

        lifetime.register_authorized_client.assert_called_once_with(":direct.test")
        lifetime.unregister_client.assert_called_once_with(":direct.test")

    def test_every_exported_method_has_the_shared_error_boundary(self):
        exported = [
            member
            for member in vars(VpnDbusService).values()
            if getattr(member, "__DBUS_METHOD", None) is not None
        ]

        self.assertTrue(exported)
        self.assertTrue(
            all(
                getattr(member, "__dbus_error_boundary__", False) for member in exported
            )
        )

    async def test_unexpected_exception_text_is_not_exposed(self):
        service, controller = make_service()
        controller.connect_country.side_effect = RuntimeError(SENTINEL)

        with self.assertLogs(
            "proton_vpn_kde_backend.dbus_service", level="ERROR"
        ) as captured:
            with self.assertRaises(DBusError) as raised:
                await type(service).connect_country.__wrapped__(service, "US")

        self.assertEqual(OPERATION_FAILED_ERROR, raised.exception.type)
        self.assertEqual(OPERATION_FAILED_MESSAGE, raised.exception.text)
        self.assertNotIn(SENTINEL, str(raised.exception))
        self.assertNotIn("Traceback", str(raised.exception))
        log_output = "\n".join(captured.output)
        self.assertIn("RuntimeError", log_output)
        self.assertNotIn(SENTINEL, log_output)

    async def test_backend_authored_validation_message_is_preserved(self):
        service, controller = make_service()
        message = "The settings update contains an unsupported field"
        controller.update_settings_json.side_effect = UserVisibleValueError(message)

        with self.assertRaises(DBusError) as raised:
            await type(service).update_settings.__wrapped__(service, "{}")

        self.assertEqual(INVALID_SETTINGS_ERROR, raised.exception.type)
        self.assertEqual(message, raised.exception.text)

    async def test_recovery_state_blocks_dbus_credentials_and_protection_mutation(self):
        adapter = DemoCoreAdapter(logged_in=False, kill_switch=2)
        adapter._auth_state = "protection_unknown"
        adapter._snapshot = adapter._build_snapshot(message="Restart required")
        adapter.login = AsyncMock()
        adapter.disable_kill_switch_for_login = AsyncMock()
        controller = BackendController(adapter)
        self.assertTrue(await controller.start())
        service = VpnDbusService(controller)
        service._read_secret = Mock(  # type: ignore[method-assign]
            return_value={"username": "demo-user", "password": "password"}
        )

        with self.assertRaises(DBusError) as login_error:
            await type(service).login.__wrapped__(service, 0)
        self.assertEqual(OPERATION_FAILED_ERROR, login_error.exception.type)
        self.assertIn("Restart the Proton backend", login_error.exception.text)
        adapter.login.assert_not_awaited()

        with self.assertRaises(DBusError) as settings_error:
            await type(service).disable_kill_switch_for_login.__wrapped__(service)
        self.assertEqual(INVALID_SETTINGS_ERROR, settings_error.exception.type)
        self.assertIn("Restart the Proton backend", settings_error.exception.text)
        adapter.disable_kill_switch_for_login.assert_not_awaited()

    async def test_capability_connect_is_forwarded_without_interpretation(self):
        service, controller = make_service()

        await type(service).connect_fastest_with_feature.__wrapped__(
            service, "streaming"
        )

        controller.connect_fastest_with_feature.assert_awaited_once_with("streaming")

        await type(service).connect_fastest_with_features.__wrapped__(
            service, ["p2p", "streaming"]
        )
        controller.connect_fastest_with_features.assert_awaited_once_with(
            ["p2p", "streaming"]
        )

        await type(service).connect_country_with_features.__wrapped__(
            service, "CH", ["secure-core", "p2p"]
        )
        controller.connect_country_with_features.assert_awaited_once_with(
            "CH", ["secure-core", "p2p"]
        )

        await type(service).connect_group_with_features.__wrapped__(
            service, "CH", "location", "Zurich", ["p2p", "streaming"]
        )
        controller.connect_group_with_features.assert_awaited_once_with(
            "CH", "location", "Zurich", ["p2p", "streaming"]
        )

    async def test_unsafe_user_visible_message_falls_back(self):
        service, controller = make_service()
        controller.update_settings_json.side_effect = UserVisibleValueError(
            f"{SENTINEL}\nTraceback"
        )

        with self.assertRaises(DBusError) as raised:
            await type(service).update_settings.__wrapped__(service, "{}")

        self.assertEqual(INVALID_SETTINGS_ERROR, raised.exception.type)
        self.assertEqual(
            "The VPN setting could not be changed",
            raised.exception.text,
        )
        self.assertNotIn(SENTINEL, str(raised.exception))

    async def test_nps_completion_unknown_has_a_non_retryable_error_class(self):
        service, controller = make_service()
        controller.submit_nps_survey = AsyncMock(
            side_effect=NpsCompletionUnknownError(
                "accepted before private upstream details"
            )
        )
        service._read_secret = Mock(  # type: ignore[method-assign]
            return_value={
                "score": "9",
                "comments": "Works well on Plasma",
                "responseType": "submit",
            }
        )

        with self.assertRaises(DBusError) as raised:
            await type(service).submit_nps_survey.__wrapped__(service, 0)

        self.assertEqual(NPS_COMPLETION_UNKNOWN_ERROR, raised.exception.type)
        self.assertEqual(
            "Survey submission completion could not be confirmed",
            raised.exception.text,
        )

    async def test_support_report_submission_is_disabled_by_default(self):
        service, controller = make_service()
        controller.submit_support_report = AsyncMock()

        descriptor = create_test_fd("disabled-support-report")
        with self.assertRaises(DBusError) as raised:
            await type(service).submit_support_report.__wrapped__(service, descriptor)

        self.assertEqual(INVALID_SUPPORT_REPORT_ERROR, raised.exception.type)
        self.assertEqual(SUPPORT_REPORT_DISABLED_MESSAGE, raised.exception.text)
        controller.submit_support_report.assert_not_awaited()
        with self.assertRaises(OSError):
            os.fstat(descriptor)


if __name__ == "__main__":
    unittest.main()
