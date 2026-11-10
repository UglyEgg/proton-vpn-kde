# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Only synthetic providers; never unlock, create collections, or access secrets."""

import asyncio
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from dbus_fast import Message, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, MessageFlag, MessageType, NameFlag, RequestNameReply

from proton_vpn_kde_backend.secret_service_readiness import (
    require_secret_service_backend, secret_service_unlocked, wait_for_secret_service,
)


OWNER = ":1.42"
COLLECTION = "/org/freedesktop/secrets/collection/example"


def reply(body, sender=OWNER, message_type=MessageType.METHOD_RETURN, error_name=None):
    return SimpleNamespace(body=body, sender=sender, message_type=message_type, error_name=error_name)


class SecretServiceReadinessTests(unittest.IsolatedAsyncioTestCase):
    def test_selection_replaces_only_keyring_overrides_and_remains_idempotent(self):
        with patch.dict(os.environ, {
            "PROTON_LOADER_OVERRIDES": "transport=existing keyring=legacy keyring=-secret_service other=kept",
        }):
            require_secret_service_backend()
            self.assertEqual("transport=existing other=kept keyring=secret_service",
                             os.environ["PROTON_LOADER_OVERRIDES"])
            require_secret_service_backend()
            self.assertEqual("transport=existing other=kept keyring=secret_service",
                             os.environ["PROTON_LOADER_OVERRIDES"])

    def test_selection_needs_no_provider_or_proton_import(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("proton_vpn_kde_backend.secret_service_readiness.MessageBus") as bus:
            require_secret_service_backend()
            self.assertEqual("keyring=secret_service", os.environ["PROTON_LOADER_OVERRIDES"])
            bus.assert_not_called()

    def bus(self, locked=False, *, alias=COLLECTION, collections=None):
        replies = [reply([OWNER]), reply([os.getuid()]), reply([alias])]
        if alias == "/":
            replies.append(reply([Variant("ao", [COLLECTION] if collections is None else collections)]))
        replies += [reply([Variant("b", locked)]), reply([OWNER])]
        return SimpleNamespace(
            connect=AsyncMock(), call=AsyncMock(side_effect=replies),
            disconnect=Mock(), wait_for_disconnect=AsyncMock(), replies=replies,
        )

    async def observe(self, bus, **options):
        with patch("proton_vpn_kde_backend.secret_service_readiness.MessageBus", return_value=bus):
            result = await secret_service_unlocked(**options)
        bus.disconnect.assert_called_once()
        bus.wait_for_disconnect.assert_awaited_once()
        for call in bus.call.await_args_list:
            message = call.args[0]
            self.assertTrue(message.flags & MessageFlag.NO_AUTOSTART)
            allowed = {"GetNameOwner", "GetConnectionUnixUser", "ReadAlias", "Get"}
            if options.get("activate"):
                allowed.add("StartServiceByName")
            self.assertIn(message.member, allowed)
            if message.destination != "org.freedesktop.DBus":
                self.assertEqual(OWNER, message.destination)
        return result

    async def test_unlocked_default_is_ready_without_prompting(self):
        self.assertTrue(await self.observe(self.bus()))

    async def test_locked_collection_is_not_ready(self):
        self.assertFalse(await self.observe(self.bus(locked=True)))

    async def test_initial_admission_requests_activation_before_owner_observation(self):
        bus = self.bus()
        bus.replies.insert(0, reply([1]))
        self.assertTrue(await self.observe(bus, activate=True, allow_empty=True))
        message = bus.call.await_args_list[0].args[0]
        self.assertEqual("StartServiceByName", message.member)
        self.assertEqual("org.freedesktop.DBus", message.destination)
        self.assertEqual("su", message.signature)
        self.assertEqual(["org.freedesktop.secrets", 0], message.body)

    async def test_failed_activation_still_observes_a_manually_started_provider(self):
        bus = self.bus()
        bus.replies.insert(0, reply([], message_type=MessageType.ERROR,
                                    error_name="org.freedesktop.DBus.Error.ServiceUnknown"))
        self.assertTrue(await self.observe(bus, activate=True, allow_empty=True))

    def empty_bus(self):
        bus = self.bus(alias="/", collections=[])
        del bus.replies[4]  # No collection exists whose Locked property could be read.
        return bus

    async def test_initial_empty_service_is_admitted_for_keyring_owned_creation(self):
        self.assertTrue(await self.observe(self.empty_bus(), allow_empty=True))
        self.assertFalse(await self.observe(self.empty_bus()))

    async def test_empty_service_keeps_uid_owner_and_ambiguity_barriers(self):
        for index, value in ((1, reply([os.getuid() + 1])),
                             (3, reply([Variant("ao", [])], sender=":1.43")),
                             (4, reply([":1.43"]))):
            with self.subTest(index=index):
                bus = self.empty_bus()
                bus.replies[index] = value
                self.assertFalse(await self.observe(bus, allow_empty=True))
        self.assertFalse(await self.observe(
            self.bus(alias="/", collections=[COLLECTION, COLLECTION + "2"]), allow_empty=True))
        self.assertFalse(await self.observe(self.bus(locked=True), allow_empty=True))

    async def test_only_collection_fallback_is_provider_neutral(self):
        self.assertTrue(await self.observe(self.bus(alias="/")))
        for collections in ([], [COLLECTION, COLLECTION + "2"]):
            with self.subTest(collections=collections):
                self.assertFalse(await self.observe(self.bus(alias="/", collections=collections)))

    def stale_alias_bus(self, *, error_name="org.freedesktop.DBus.Error.UnknownObject",
                        sender=OWNER, collections=None, locked=False):
        bus = self.bus(alias=COLLECTION + "_deleted")
        bus.replies[3:] = [
            reply([], message_type=MessageType.ERROR, error_name=error_name, sender=sender),
            reply([Variant("ao", [COLLECTION] if collections is None else collections)]),
            reply([Variant("b", locked)]), reply([OWNER]),
        ]
        return bus

    async def test_stale_default_alias_uses_only_advertised_collection(self):
        for error_name in ("org.freedesktop.DBus.Error.UnknownObject",
                           "org.freedesktop.DBus.Error.UnknownMethod",
                           "org.freedesktop.Secret.Error.NoSuchObject"):
            with self.subTest(error_name=error_name):
                bus = self.stale_alias_bus(error_name=error_name)
                self.assertTrue(await self.observe(bus))
                self.assertEqual(COLLECTION, bus.call.await_args_list[-2].args[0].path)

    async def test_missing_alias_error_uses_only_advertised_collection(self):
        bus = self.stale_alias_bus()
        del bus.replies[2]  # Missing-object reply comes from ReadAlias itself.
        self.assertTrue(await self.observe(bus))

    async def test_unrelated_errors_and_wrong_sender_do_not_gain_fallback(self):
        for kwargs in ({"error_name": "org.freedesktop.DBus.Error.AccessDenied"},
                       {"sender": ":1.43"}):
            with self.subTest(kwargs=kwargs):
                bus = self.stale_alias_bus(**kwargs)
                self.assertFalse(await self.observe(bus))
                self.assertEqual(4, bus.call.await_count)

    async def test_stale_alias_fallback_retains_lock_ambiguity_and_owner_barriers(self):
        for kwargs in ({"collections": []}, {"collections": [COLLECTION, COLLECTION + "2"]},
                       {"locked": True}):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(await self.observe(self.stale_alias_bus(**kwargs)))
        bus = self.stale_alias_bus()
        bus.replies[-1] = reply([":1.43"])
        self.assertFalse(await self.observe(bus))

    async def test_foreign_uid_never_queries_provider(self):
        bus = self.bus()
        bus.replies[1] = reply([os.getuid() + 1])
        self.assertFalse(await self.observe(bus))
        self.assertEqual(2, bus.call.await_count)

    async def test_owner_replacement_or_wrong_sender_is_not_ready(self):
        for index in (2, 4):
            with self.subTest(index=index):
                bus = self.bus()
                if index == 2:
                    bus.replies[index] = reply([COLLECTION], sender=":1.43")
                else:
                    bus.replies[index] = reply([":1.43"])
                self.assertFalse(await self.observe(bus))

    async def test_malformed_properties_errors_and_absent_service_are_not_ready(self):
        for index, value in ((0, reply([], message_type=MessageType.ERROR)),
                             (1, reply([True])), (2, reply([42])),
                             (3, reply([Variant("s", "false")]))):
            with self.subTest(index=index):
                bus = self.bus()
                bus.replies[index] = value
                self.assertFalse(await self.observe(bus))

    async def test_connect_failure_closes_the_bus(self):
        bus = self.bus()
        bus.connect.side_effect = RuntimeError("private transport detail")
        self.assertFalse(await self.observe(bus))
        bus.call.assert_not_awaited()

    async def test_hung_observation_has_a_deadline(self):
        bus = self.bus()
        bus.call.side_effect = lambda _message: None
        async def blocked(_message):
            await asyncio.Event().wait()
        bus.call.side_effect = blocked
        with patch("proton_vpn_kde_backend.secret_service_readiness.QUERY_SECONDS", 0.01):
            self.assertFalse(await asyncio.wait_for(self.observe(bus), 1))

    async def test_cancellation_propagates_and_closes_the_bus(self):
        bus = self.bus()
        bus.call.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.observe(bus)
        bus.disconnect.assert_called_once()

    async def test_wait_polls_readiness_not_credentials(self):
        with (
            patch("proton_vpn_kde_backend.secret_service_readiness.secret_service_unlocked",
                  new=AsyncMock(side_effect=[False, False, True])) as probe,
            patch("proton_vpn_kde_backend.secret_service_readiness.POLL_SECONDS", 0),
        ):
            self.assertTrue(await wait_for_secret_service(1))
        self.assertEqual(3, probe.await_count)

    async def test_initial_admission_activates_only_once_within_the_shared_wait(self):
        with (
            patch("proton_vpn_kde_backend.secret_service_readiness.secret_service_unlocked",
                  new=AsyncMock(side_effect=[False, True])) as probe,
            patch("proton_vpn_kde_backend.secret_service_readiness.POLL_SECONDS", 0),
        ):
            self.assertTrue(await wait_for_secret_service(1, initial_admission=True))
        self.assertEqual({"activate": True, "allow_empty": True}, probe.await_args_list[0].kwargs)
        self.assertEqual({"activate": False, "allow_empty": True}, probe.await_args_list[1].kwargs)

    async def test_wait_exhaustion_never_prompts_or_activates(self):
        with patch("proton_vpn_kde_backend.secret_service_readiness.secret_service_unlocked",
                   new=AsyncMock(return_value=False)) as probe:
            self.assertFalse(await wait_for_secret_service(0))
            probe.assert_not_awaited()
            self.assertFalse(await wait_for_secret_service(0.01))


@unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_PRIVATE_SECRET_SERVICE") == "1",
                     "explicit private dbus-run-session fixture required")
class PrivateSecretServiceWireTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_bus_observes_only_the_fake_collection(self):
        # Never claim the provider name on a desktop bus, even when a caller
        # accidentally enables this opt-in test in their ordinary environment.
        self.assertEqual("/usr/bin/dbus-run-session", os.readlink(f"/proc/{os.getppid()}/exe"))
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        locked, alias, observed = [True], [COLLECTION], []
        collections = [COLLECTION]
        def handle(message):
            if message.message_type is not MessageType.METHOD_CALL:
                return None
            if message.path not in {"/org/freedesktop/secrets", COLLECTION, COLLECTION + "_deleted"}:
                return None
            observed.append((message.member, message.body))
            if message.member == "ReadAlias" and message.body == ["default"]:
                return Message.new_method_return(message, "o", [alias[0]])
            if message.member == "Get" and message.body == ["org.freedesktop.Secret.Collection", "Locked"]:
                if message.path == COLLECTION + "_deleted":
                    return Message.new_error(message, "org.freedesktop.DBus.Error.UnknownObject", "missing")
                return Message.new_method_return(message, "v", [Variant("b", locked[0])])
            if message.member == "Get" and message.body == ["org.freedesktop.Secret.Service", "Collections"]:
                return Message.new_method_return(message, "v", [Variant("ao", list(collections))])
            raise AssertionError("Passive observation requested a mutation or secret")
        try:
            owner = await bus.request_name("org.freedesktop.secrets", NameFlag.DO_NOT_QUEUE)
            self.assertEqual(RequestNameReply.PRIMARY_OWNER, owner)
            bus.add_message_handler(handle)
            self.assertFalse(await secret_service_unlocked())
            locked[0] = False
            self.assertTrue(await secret_service_unlocked())
            alias[0] = "/"
            self.assertTrue(await secret_service_unlocked())
            alias[0] = COLLECTION + "_deleted"
            self.assertTrue(await secret_service_unlocked())
            alias[0] = "/"
            collections.clear()
            self.assertFalse(await secret_service_unlocked())
            self.assertTrue(await secret_service_unlocked(activate=True, allow_empty=True))
            self.assertTrue(observed)
            self.assertTrue(all(member in {"ReadAlias", "Get"} for member, _body in observed))
        finally:
            bus.disconnect()
            await bus.wait_for_disconnect()
