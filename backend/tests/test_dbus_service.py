from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock

from dbus_fast.errors import DBusError

from proton_vpn_kde_backend.dbus_service import (
    INVALID_SETTINGS_ERROR,
    OPERATION_FAILED_ERROR,
    OPERATION_FAILED_MESSAGE,
    VpnDbusService,
)
from proton_vpn_kde_backend.errors import UserVisibleValueError


SENTINEL = "credential=must-not-cross-dbus /workspace/private.py"


def make_service() -> tuple[VpnDbusService, Mock]:
    controller = Mock()
    controller.connect_country = AsyncMock()
    controller.update_settings_json = AsyncMock()
    service = VpnDbusService(controller)
    return service, controller


class VpnDbusServiceTests(unittest.IsolatedAsyncioTestCase):
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


if __name__ == "__main__":
    unittest.main()
