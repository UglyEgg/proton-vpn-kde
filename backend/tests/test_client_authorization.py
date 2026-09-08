# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from dbus_fast import Message
from dbus_fast.constants import MessageType

from fd_helpers import create_test_fd
from proton_vpn_kde_backend.client_authorization import (
    BACKEND_INTERFACE,
    BACKEND_OBJECT_PATH,
    ClientAuthorizer,
    INVALID_ARGUMENTS_ERROR,
    INVALID_SECRET_ERROR,
    UNAUTHORIZED_ERROR,
    process_environment_is_safe,
)
from proton_vpn_kde_backend.dbus_contract import CLASSIFIED_METHODS, SECRET_DESCRIPTOR_METHODS
from proton_vpn_kde_backend.environment_contract import (
    UNSAFE_ENVIRONMENT_NAMES,
)
from proton_vpn_kde_backend.dbus_service import exported_method_names
from proton_vpn_kde_backend.features import TRUSTED_CLIENT_EXECUTABLES


def method_message(
    member: str,
    *,
    sender: str = ":1.40",
    interface: str | None = BACKEND_INTERFACE,
    signature: str = "",
    body: list[object] | None = None,
    unix_fds: list[int] | None = None,
    path: str = BACKEND_OBJECT_PATH,
) -> Message:
    return Message(
        path=path,
        interface=interface,
        member=member,
        message_type=MessageType.METHOD_CALL,
        sender=sender,
        serial=1,
        signature=signature,
        body=body or [],
        unix_fds=unix_fds or [],
    )


class ClientAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def test_non_consuming_routes_discharge_ownership_without_consuming_messages(self):
        messages = [
            method_message("Ping", path="/other"),
            Message.new_signal("/other", "test.Events", "Changed"),
            Message.new_method_return(method_message("GetSnapshot")),
            Message.new_error(method_message("GetSnapshot"), "test.Error", "test"),
        ]
        authorizer = ClientAuthorizer(None, ())
        for message in messages:
            with self.subTest(message_type=message.message_type):
                descriptor = create_test_fd("unadopted-message")
                message.unix_fds = [descriptor]
                original_body = message.body
                with patch("os.close", wraps=os.close) as close:
                    self.assertIsNone(authorizer.message_handler(message))
                    self.assertIsNone(authorizer.message_handler(message))
                    close.assert_called_once_with(descriptor)
                self.assertEqual([], message.unix_fds)
                self.assertIs(original_body, message.body)
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    async def test_all_protected_descriptor_consumers_retain_ownership_until_adoption(self):
        authorizer = ClientAuthorizer(None, (), enforce_identity=False)
        for member in SECRET_DESCRIPTOR_METHODS:
            for interface in (BACKEND_INTERFACE, None):
                with self.subTest(member=member, interface=interface):
                    descriptor = create_test_fd("adopted-message")
                    try:
                        message = method_message(member, interface=interface,
                                                 signature="h", body=[0],
                                                 unix_fds=[descriptor])
                        self.assertIsNone(authorizer.message_handler(message))
                        self.assertEqual([descriptor], message.unix_fds)
                        os.fstat(descriptor)
                    finally:
                        os.close(descriptor)

    def test_shutdown_closes_descriptors_even_for_previously_authorized_consumers(self):
        authorizer = ClientAuthorizer(None, (), enforce_identity=False)
        authorizer.message_handler(method_message("AuthorizeClient"))
        authorizer.close_ingress()
        descriptor = create_test_fd("shutdown-message")
        message = method_message("Login", signature="h", body=[0], unix_fds=[descriptor])
        self.assertEqual(UNAUTHORIZED_ERROR, authorizer.message_handler(message).error_name)
        self.assertEqual([], message.unix_fds)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_supported_representations_share_the_same_authorization_policy(self):
        for interface in (BACKEND_INTERFACE, None):
            with self.subTest(interface=interface):
                authorizer = ClientAuthorizer(None, ())
                denied = authorizer.message_handler(
                    method_message("GetAuthPublicKey", interface=interface,
                                   signature="s", body=["Login"])
                )
                self.assertEqual(UNAUTHORIZED_ERROR, denied.error_name)
                self.assertIsNone(authorizer.message_handler(
                    method_message("GetSnapshot", interface=interface)
                ))

    def test_standard_interfaces_preserve_calls_and_reject_ancillary_descriptors(self):
        for interface, member in (
            ("org.freedesktop.DBus.Introspectable", "Introspect"),
            ("org.freedesktop.DBus.Peer", "Ping"),
            ("org.freedesktop.DBus.Properties", "GetAll"),
            ("org.freedesktop.DBus.ObjectManager", "GetManagedObjects"),
        ):
            with self.subTest(interface=interface):
                authorizer = ClientAuthorizer(None, ())
                self.assertIsNone(authorizer.message_handler(
                    method_message(member, interface=interface)
                ))
                descriptor = create_test_fd("standard-rejection")
                rejected = authorizer.message_handler(method_message(
                    member, interface=interface, unix_fds=[descriptor]
                ))
                self.assertEqual(INVALID_ARGUMENTS_ERROR, rejected.error_name)
                with self.assertRaises(OSError):
                    os.fstat(descriptor)


    def test_unsafe_environment_contract_is_complete_and_unique(self):
        self.assertEqual(len(UNSAFE_ENVIRONMENT_NAMES), len(set(UNSAFE_ENVIRONMENT_NAMES)))
        self.assertTrue(
            {
                "OPENSSL_CONF",
                "OPENSSL_CONF_INCLUDE",
                "OPENSSL_MODULES",
                "OPENSSL_ENGINES",
                "GI_TYPELIB_PATH",
                "GIO_EXTRA_MODULES",
                "GIO_MODULE_DIR",
                "GCONV_PATH",
            }.issubset(UNSAFE_ENVIRONMENT_NAMES)
        )

    def test_every_unsafe_environment_name_is_rejected(self):
        for name in UNSAFE_ENVIRONMENT_NAMES:
            with self.subTest(name=name):
                for value in (b"", b"/tmp/attacker"):
                    self.assertFalse(
                        process_environment_is_safe(
                            [b"HOME=/home/test", f"{name}=".encode() + value]
                        )
                    )

    def test_environment_near_misses_and_ordinary_values_are_allowed(self):
        self.assertTrue(
            process_environment_is_safe(
                [
                    b"HOME=/home/test",
                    b"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus",
                    b"OPENSSL_CONFUSION=/tmp/ordinary",
                ]
            )
        )

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
        descriptor = create_test_fd("authorization-rejection")

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
        descriptor = create_test_fd("unexpected-read-fd")

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
        first = create_test_fd("secret-first")
        second = create_test_fd("secret-second")

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

    async def test_authorization_timeout_clears_provisional_identity_state(self):
        never_finishes = asyncio.Event()

        async def identity_probe(_sender: str) -> bool:
            await never_finishes.wait()
            return True

        authorizer = ClientAuthorizer(
            None,
            (),
            identity_probe=identity_probe,
            owner_probe=AsyncMock(return_value=True),
            authorization_timeout=0.01,
        )
        authorizer.message_handler(method_message("AuthorizeClient"))

        with self.assertRaises(PermissionError):
            await authorizer.authorize(":1.40")

        self.assertFalse(authorizer.authorized_senders)
        self.assertFalse(authorizer._pending_authorizations)
        self.assertFalse(authorizer._revoked_while_pending)

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
        descriptor = create_test_fd("owner-loss")

        authorizer.message_handler(
            Message(
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="NameOwnerChanged",
                message_type=MessageType.SIGNAL,
                sender="org.freedesktop.DBus",
                signature="sss",
                body=[":1.40", ":1.40", ""],
                unix_fds=[descriptor],
            )
        )

        self.assertNotIn(":1.40", authorizer.authorized_senders)
        self.assertEqual([":1.40"], revoked)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    async def test_name_owner_loss_during_probe_cannot_authorize_stale_sender(self):
        probe_started = asyncio.Event()
        release_probe = asyncio.Event()

        async def delayed_identity_probe(_sender: str) -> bool:
            probe_started.set()
            await release_probe.wait()
            return True

        authorizer = ClientAuthorizer(
            None,
            (),
            identity_probe=delayed_identity_probe,
            owner_probe=AsyncMock(return_value=True),
        )
        authorizer.message_handler(method_message("AuthorizeClient"))
        authorization = asyncio.create_task(authorizer.authorize(":1.40"))
        await probe_started.wait()

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
        release_probe.set()

        with self.assertRaises(PermissionError):
            await authorization
        self.assertNotIn(":1.40", authorizer.authorized_senders)
        self.assertFalse(authorizer._pending_authorizations)
        self.assertFalse(authorizer._revoked_while_pending)


if __name__ == "__main__":
    unittest.main()
