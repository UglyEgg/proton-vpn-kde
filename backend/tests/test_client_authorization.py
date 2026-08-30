# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock

from dbus_fast import Message
from dbus_fast.constants import MessageType

from proton_vpn_kde_backend.client_authorization import (
    BACKEND_INTERFACE,
    BACKEND_OBJECT_PATH,
    ClientAuthorizer,
    INVALID_ARGUMENTS_ERROR,
    INVALID_SECRET_ERROR,
    UNAUTHORIZED_ERROR,
)
from proton_vpn_kde_backend.dbus_contract import CLASSIFIED_METHODS
from proton_vpn_kde_backend.dbus_service import exported_method_names
from proton_vpn_kde_backend.features import TRUSTED_CLIENT_EXECUTABLES


def method_message(
    member: str,
    *,
    sender: str = ":1.40",
    signature: str = "",
    body: list[object] | None = None,
    unix_fds: list[int] | None = None,
) -> Message:
    return Message(
        path=BACKEND_OBJECT_PATH,
        interface=BACKEND_INTERFACE,
        member=member,
        message_type=MessageType.METHOD_CALL,
        sender=sender,
        serial=1,
        signature=signature,
        body=body or [],
        unix_fds=unix_fds or [],
    )


class ClientAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def test_shared_plugin_hosts_are_not_trusted_clients(self):
        self.assertNotIn(
            "krunner",
            {os.path.basename(path) for path in TRUSTED_CLIENT_EXECUTABLES},
        )

    def test_every_export_is_explicitly_classified(self):
        self.assertEqual(CLASSIFIED_METHODS, exported_method_names())

    def test_unauthorized_mutation_is_rejected_and_closes_received_fds(self):
        authorizer = ClientAuthorizer(
            None, (), identity_probe=AsyncMock(), owner_probe=AsyncMock()
        )
        descriptor = os.memfd_create("authorization-rejection", os.MFD_CLOEXEC)

        result = authorizer.message_handler(
            method_message(
                "Login",
                signature="h",
                body=[0],
                unix_fds=[descriptor],
            )
        )

        self.assertIsInstance(result, Message)
        self.assertEqual(UNAUTHORIZED_ERROR, result.error_name)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_read_only_method_rejects_and_closes_ancillary_fds(self):
        authorizer = ClientAuthorizer(
            None, (), identity_probe=AsyncMock(), owner_probe=AsyncMock()
        )
        descriptor = os.memfd_create("unexpected-read-fd", os.MFD_CLOEXEC)

        result = authorizer.message_handler(
            method_message("GetSnapshot", unix_fds=[descriptor])
        )

        self.assertIsInstance(result, Message)
        self.assertEqual(INVALID_ARGUMENTS_ERROR, result.error_name)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_secret_method_rejects_and_closes_unreferenced_descriptors(self):
        authorizer = ClientAuthorizer(
            None, (), identity_probe=AsyncMock(), owner_probe=AsyncMock()
        )
        first = os.memfd_create("secret-first", os.MFD_CLOEXEC)
        second = os.memfd_create("secret-second", os.MFD_CLOEXEC)

        result = authorizer.message_handler(
            method_message(
                "Login",
                signature="h",
                body=[1],
                unix_fds=[first, second],
            )
        )

        self.assertIsInstance(result, Message)
        self.assertEqual(INVALID_SECRET_ERROR, result.error_name)
        for descriptor in (first, second):
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    async def test_authorization_is_bound_to_actual_sender(self):
        probe = AsyncMock(return_value=True)
        authorizer = ClientAuthorizer(
            None, (), identity_probe=probe, owner_probe=AsyncMock(return_value=True)
        )
        authorizer.message_handler(method_message("AuthorizeClient"))

        with self.assertRaises(PermissionError):
            await authorizer.authorize(":1.41")

        self.assertFalse(authorizer.authorized_senders)
        probe.assert_not_awaited()

    async def test_authenticated_sender_can_mutate_but_another_caller_cannot(self):
        authorizer = ClientAuthorizer(
            None,
            (),
            identity_probe=AsyncMock(return_value=True),
            owner_probe=AsyncMock(return_value=True),
        )
        authorizer.message_handler(method_message("AuthorizeClient"))
        await authorizer.authorize(":1.40")

        self.assertIsNone(authorizer.message_handler(method_message("Logout")))
        rejected = authorizer.message_handler(method_message("Logout", sender=":1.41"))
        self.assertEqual(UNAUTHORIZED_ERROR, rejected.error_name)

    async def test_name_owner_loss_revokes_authorization(self):
        authorizer = ClientAuthorizer(
            None,
            (),
            identity_probe=AsyncMock(return_value=True),
            owner_probe=AsyncMock(return_value=True),
        )
        authorizer.message_handler(method_message("AuthorizeClient"))
        await authorizer.authorize(":1.40")
        revoked: list[str] = []
        authorizer.subscribe_revocation(revoked.append)

        authorizer.message_handler(
            Message(
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="NameOwnerChanged",
                message_type=MessageType.SIGNAL,
                sender="org.freedesktop.DBus",
                signature="sss",
                body=[":1.40", ":1.40", ""],
            )
        )

        self.assertNotIn(":1.40", authorizer.authorized_senders)
        self.assertEqual([":1.40"], revoked)


if __name__ == "__main__":
    unittest.main()
