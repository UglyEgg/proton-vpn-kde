# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Synthetic unlock protocols; the desktop provider is never contacted."""

import asyncio
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from dbus_fast import Message, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, MessageType, NameFlag, RequestNameReply

from proton_vpn_kde_backend import secret_service_readiness as readiness


SERVICE = "org.freedesktop.secrets"
INTERFACE = "org.freedesktop.Secret.Service"
PROMPT_INTERFACE = "org.freedesktop.Secret.Prompt"
COLLECTION = "/wallet/collection/main"
PROMPT = "/wallet/prompt/unlock"


class FakeUnlockBus:
    """A protocol boundary, with explicit completion/cancellation controls."""

    def __init__(self, mode="success"):
        self.owner = ":1.42"
        self.current_owner = self.owner
        self.uid = os.getuid()
        self.locked = True
        self.mode = mode
        self.messages = []
        self.handlers = []
        self.shown = asyncio.Event()
        self.unlock_called = asyncio.Event()
        self.block_prompt_reply = False
        self.block_dismiss = False
        self.before_call = None
        self.reply_sender = None
        self.collections = [COLLECTION]
        self.alias = COLLECTION
        self.connect = AsyncMock()
        self.disconnect = Mock()
        self.wait_for_disconnect = AsyncMock()

    def add_message_handler(self, handler):
        self.handlers.append(handler)

    def remove_message_handler(self, handler):
        self.handlers.remove(handler)

    def members(self, member):
        return [m for m in self.messages if m.member == member]

    def emit(self, **overrides):
        values = dict(message_type=MessageType.SIGNAL, sender=self.owner,
                      path=PROMPT, interface=PROMPT_INTERFACE, member="Completed",
                      signature="bv", body=[False, Variant("ao", [COLLECTION])])
        values.update(overrides)
        for handler in tuple(self.handlers):
            handler(SimpleNamespace(**values))

    def complete(self, *, dismissed=False):
        if not dismissed:
            self.locked = False
        self.emit(body=[dismissed, Variant("ao", [] if dismissed else [COLLECTION])])

    def replace_owner(self):
        self.current_owner = ":1.99"
        self.emit(sender="org.freedesktop.DBus", path="/org/freedesktop/DBus",
                  interface="org.freedesktop.DBus", member="NameOwnerChanged",
                  signature="sss", body=[SERVICE, self.owner, self.current_owner])

    async def call(self, message):
        self.messages.append(message)
        if self.before_call:
            self.before_call(message)
        sender = message.destination
        if message.member == "StartServiceByName":
            body = [2]
        elif message.member == "AddMatch":
            body = []
        elif message.member == "GetNameOwner":
            body = [self.current_owner]
        elif message.member == "GetConnectionUnixUser":
            body = [self.uid]
        elif message.member == "ReadAlias":
            body = [self.alias if len(self.collections) == 1 else "/"]
        elif message.member == "Get":
            if message.body == [INTERFACE, "Collections"]:
                body = [Variant("ao", self.collections)]
            else:
                assert message.body == ["org.freedesktop.Secret.Collection", "Locked"]
                if message.path == COLLECTION + "_deleted":
                    return SimpleNamespace(sender=sender, message_type=MessageType.ERROR,
                                           error_name="org.freedesktop.DBus.Error.UnknownObject")
                body = [Variant("b", self.locked)]
        elif message.member == "Unlock":
            assert message.interface == INTERFACE and message.body == [[COLLECTION]]
            self.unlock_called.set()
            if self.mode == "unsupported":
                return SimpleNamespace(sender=sender, message_type=MessageType.ERROR,
                                       error_name="org.freedesktop.DBus.Error.UnknownMethod")
            if self.mode in {"immediate", "false-claim", "unavailable"}:
                self.locked = self.mode != "immediate"
                body = [[COLLECTION] if self.mode != "unavailable" else [], "/"]
            else:
                body = [[], PROMPT]
        elif message.member == "Prompt":
            assert message.interface == PROMPT_INTERFACE and message.body == [""]
            self.shown.set()
            if self.mode == "success":
                self.complete()  # Completion deliberately precedes the method reply.
            elif self.mode == "dismissed":
                self.complete(dismissed=True)
            if self.block_prompt_reply:
                await asyncio.Event().wait()
            body = []
        elif message.member == "Dismiss":
            assert message.interface == PROMPT_INTERFACE and message.path == PROMPT
            if self.block_dismiss:
                await asyncio.Event().wait()
            body = []
        else:
            raise AssertionError("Unexpected operation: " + message.member)
        if self.reply_sender:
            sender = self.reply_sender(message, sender)
        return SimpleNamespace(body=body, sender=sender, message_type=MessageType.METHOD_RETURN)


class SecretServiceUnlockTests(unittest.IsolatedAsyncioTestCase):
    def setup_bus(self, mode="success"):
        bus = FakeUnlockBus(mode)
        self.enterContext(patch.object(readiness, "MessageBus", return_value=bus))
        self.enterContext(patch.object(readiness, "POLL_SECONDS", 0.005))
        self.addCleanup(lambda: self.assertEqual([], bus.handlers))
        return bus

    async def wait(self, timeout=0.1, *, initial=True, prompt=True):
        return await readiness.wait_for_secret_service(
            timeout, initial_admission=initial, request_unlock=prompt)

    async def test_fast_completion_before_prompt_reply_is_not_lost(self):
        bus = self.setup_bus()
        self.assertTrue(await self.wait())
        self.assertEqual(1, len(bus.members("Unlock")))
        self.assertEqual(1, len(bus.members("Prompt")))
        self.assertEqual([], bus.members("Dismiss"))
        self.assertEqual(2, len(bus.members("Get")))
        for message in bus.members("Unlock") + bus.members("Prompt"):
            self.assertEqual(bus.owner, message.destination)
        self.assertTrue(bus.members("AddMatch"))

    async def test_immediate_unlock_needs_no_dialog_but_is_reobserved(self):
        bus = self.setup_bus("immediate")
        self.assertTrue(await self.wait())
        self.assertEqual([], bus.members("Prompt"))
        self.assertEqual(2, len(bus.members("Get")))

    async def test_missing_or_stale_alias_unlocks_only_the_advertised_collection(self):
        for alias in ("/", COLLECTION + "_deleted"):
            with self.subTest(alias=alias):
                bus = self.setup_bus()
                bus.alias = alias
                self.assertTrue(await self.wait())
                self.assertEqual([[COLLECTION]], bus.members("Unlock")[0].body)
                self.assertEqual(1, len(bus.members("Prompt")))

    async def test_unlocked_metadata_not_a_claimed_result_controls_admission(self):
        bus = self.setup_bus("false-claim")
        self.assertFalse(await self.wait(0.02))
        self.assertEqual(1, len(bus.members("Unlock")))
        self.assertEqual([], bus.members("Prompt"))

    async def test_unsupported_or_unavailable_unlock_falls_back_without_reprompting(self):
        for mode in ("unsupported", "unavailable"):
            with self.subTest(mode=mode):
                bus = self.setup_bus(mode)
                task = asyncio.create_task(self.wait())
                await asyncio.wait_for(bus.unlock_called.wait(), 1)
                bus.locked = False  # Independent manual unlock remains supported.
                self.assertTrue(await task)
                self.assertEqual(1, len(bus.members("Unlock")))
                self.assertEqual([], bus.members("Prompt"))

    async def test_explicit_dismissal_ends_admission_instead_of_retrying(self):
        bus = self.setup_bus("dismissed")
        self.assertFalse(await asyncio.wait_for(self.wait(5), 0.5))
        bus.locked = False
        self.assertEqual(1, len(bus.members("Unlock")))
        self.assertEqual(1, len(bus.members("Prompt")))
        self.assertEqual([], bus.members("Dismiss"))

    async def test_deadline_dismisses_the_pending_provider_dialog(self):
        bus = self.setup_bus("pending")
        self.assertFalse(await asyncio.wait_for(self.wait(0.02), 0.5))
        self.assertEqual(1, len(bus.members("Dismiss")))
        bus.disconnect.assert_called_once()

    async def test_cancellation_dismisses_and_ignores_late_completion(self):
        bus = self.setup_bus("pending")
        task = asyncio.create_task(self.wait(5))
        await asyncio.wait_for(bus.shown.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(1, len(bus.members("Dismiss")))
        bus.complete()
        self.assertTrue(task.cancelled())
        bus.disconnect.assert_called_once()

    async def test_cancellation_while_prompt_rpc_is_pending_still_dismisses(self):
        bus = self.setup_bus("pending")
        bus.block_prompt_reply = True
        task = asyncio.create_task(self.wait(5))
        await asyncio.wait_for(bus.shown.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(1, len(bus.members("Dismiss")))

    async def test_dialog_uses_admission_deadline_and_can_finish_before_rpc_reply(self):
        bus = self.setup_bus("pending")
        bus.block_prompt_reply = True
        with patch.object(readiness, "QUERY_SECONDS", 0.01):
            task = asyncio.create_task(self.wait(1))
            await asyncio.wait_for(bus.shown.wait(), 1)
            await asyncio.sleep(0.03)
            self.assertFalse(task.done())
            bus.complete()
            self.assertTrue(await asyncio.wait_for(task, 0.5))
        self.assertEqual([], bus.members("Dismiss"))

    async def test_owner_loss_ends_a_blocked_prompt_rpc(self):
        bus = self.setup_bus("pending")
        bus.block_prompt_reply = True
        task = asyncio.create_task(self.wait(0.03))
        await asyncio.wait_for(bus.shown.wait(), 1)
        bus.replace_owner()
        self.assertFalse(await asyncio.wait_for(task, 0.5))
        self.assertEqual(1, len(bus.members("Dismiss")))
        self.assertEqual(1, len(bus.members("Prompt")))

    async def test_hung_dismiss_and_disconnect_cannot_extend_the_wait_indefinitely(self):
        bus = self.setup_bus("pending")
        bus.block_dismiss = True
        async def hang():
            await asyncio.Event().wait()
        bus.wait_for_disconnect.side_effect = hang
        with patch.object(readiness, "CLEANUP_SECONDS", 0.01):
            self.assertFalse(await asyncio.wait_for(self.wait(0.02), 0.5))
        self.assertEqual(1, len(bus.members("Dismiss")))
        bus.disconnect.assert_called_once()

    async def test_wrong_sender_path_interface_or_signature_cannot_complete_prompt(self):
        for fields in ({"sender": ":1.999"}, {"path": PROMPT + "_other"},
                       {"interface": "wrong.interface"}, {"signature": "sv"},
                       {"body": ["false", Variant("ao", [COLLECTION])]}):
            with self.subTest(fields=fields):
                bus = self.setup_bus("pending")
                task = asyncio.create_task(self.wait())
                await asyncio.wait_for(bus.shown.wait(), 1)
                bus.emit(**fields)
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                bus.complete()
                self.assertTrue(await task)

    async def test_malformed_result_cannot_admit_and_prompt_is_retired(self):
        bus = self.setup_bus("pending")
        task = asyncio.create_task(self.wait(0.03))
        await asyncio.wait_for(bus.shown.wait(), 1)
        bus.emit(body=[False, Variant("s", "untrusted")])
        self.assertFalse(await task)
        self.assertEqual(1, len(bus.members("Unlock")))
        self.assertEqual(1, len(bus.members("Dismiss")))

    async def test_replacement_owner_does_not_receive_another_unlock_request(self):
        bus = self.setup_bus("pending")
        task = asyncio.create_task(self.wait(0.03))
        await asyncio.wait_for(bus.shown.wait(), 1)
        bus.replace_owner()
        self.assertFalse(await task)
        self.assertEqual(1, len(bus.members("Unlock")))
        self.assertEqual(bus.owner, bus.members("Dismiss")[0].destination)

    async def test_owner_change_before_dispatch_cannot_start_unlock(self):
        bus = self.setup_bus()
        def replace(message):
            if message.member == "AddMatch":
                bus.replace_owner()
        bus.before_call = replace
        self.assertFalse(await self.wait(0.02))
        self.assertEqual([], bus.members("Unlock"))

    async def test_forged_unlock_reply_is_not_used(self):
        bus = self.setup_bus()
        bus.reply_sender = lambda m, sender: ":1.999" if m.member == "Unlock" else sender
        self.assertFalse(await self.wait(0.02))
        self.assertEqual([], bus.members("Prompt"))
        self.assertEqual(1, len(bus.members("Unlock")))

    async def test_lock_retry_and_protected_cleanup_are_passive(self):
        for initial, prompt in ((False, True), (True, False)):
            with self.subTest(initial=initial, prompt=prompt):
                bus = self.setup_bus()
                self.assertFalse(await self.wait(0.02, initial=initial, prompt=prompt))
                self.assertEqual([], bus.members("Unlock"))
                self.assertEqual([], bus.members("Prompt"))

    async def test_foreign_or_ambiguous_store_never_receives_unlock(self):
        for foreign in (True, False):
            bus = self.setup_bus()
            if foreign:
                bus.uid += 1
            else:
                bus.collections = [COLLECTION, COLLECTION + "2"]
            self.assertFalse(await self.wait(0.02))
            self.assertEqual([], bus.members("Unlock"))

    async def test_already_unlocked_and_empty_stores_need_no_unlock_request(self):
        for empty in (False, True):
            bus = self.setup_bus()
            if empty:
                bus.collections = []
            else:
                bus.locked = False
            self.assertTrue(await self.wait())
            self.assertEqual([], bus.members("Unlock"))


@unittest.skipUnless(os.environ.get("PLASMA_VPN_TEST_PRIVATE_SECRET_SERVICE") == "1",
                     "explicit private dbus-run-session fixture required")
class PrivateUnlockWireTests(unittest.IsolatedAsyncioTestCase):
    async def run_protocol(self, outcome):
        self.assertEqual("/usr/bin/dbus-run-session", os.readlink(f"/proc/{os.getppid()}/exe"))
        provider = await MessageBus(bus_type=BusType.SESSION).connect()
        locked, seen, shown = [True], [], asyncio.Event()
        def handle(message):
            if message.message_type is not MessageType.METHOD_CALL:
                return
            if message.path not in {"/org/freedesktop/secrets", COLLECTION, PROMPT}:
                return
            seen.append(message.member)
            if message.member == "ReadAlias":
                return Message.new_method_return(message, "o", ["/" if outcome == "sole" else COLLECTION])
            if message.member == "Get":
                if message.body == [INTERFACE, "Collections"]:
                    return Message.new_method_return(message, "v", [Variant("ao", [COLLECTION])])
                return Message.new_method_return(message, "v", [Variant("b", locked[0])])
            if message.member == "Unlock":
                self.assertEqual([[COLLECTION]], message.body)
                return Message.new_method_return(message, "aoo", [[], PROMPT])
            if message.member == "Prompt":
                shown.set()
                if outcome == "replacement":
                    asyncio.create_task(provider.release_name(SERVICE))
                elif outcome != "timeout":
                    locked[0] = outcome not in {"success", "signal-only", "sole"}
                    provider.send(Message.new_signal(PROMPT, PROMPT_INTERFACE, "Completed", "bv",
                                  [outcome == "dismissed", Variant("ao", [] if locked[0] else [COLLECTION])]))
                if outcome == "signal-only":
                    return True  # Handled, but deliberately never reply to Prompt().
                return Message.new_method_return(message)
            if message.member == "Dismiss":
                return Message.new_method_return(message)
            raise AssertionError("Unexpected provider operation: " + message.member)
        try:
            self.assertEqual(RequestNameReply.PRIMARY_OWNER,
                             await provider.request_name(SERVICE, NameFlag.DO_NOT_QUEUE))
            provider.add_message_handler(handle)
            result = await readiness.wait_for_secret_service(
                0.1 if outcome in {"timeout", "replacement"} else 2,
                initial_admission=True, request_unlock=True)
            self.assertEqual(outcome in {"success", "signal-only", "sole"}, result)
            self.assertTrue(shown.is_set())
            self.assertEqual(1, seen.count("Unlock"))
            self.assertEqual(1, seen.count("Prompt"))
            self.assertEqual(int(outcome in {"timeout", "replacement"}), seen.count("Dismiss"))
            self.assertTrue(set(seen) <= {"ReadAlias", "Get", "Unlock", "Prompt", "Dismiss"})
        finally:
            provider.disconnect()
            await provider.wait_for_disconnect()

    async def test_real_bus_delivers_completion_before_prompt_reply(self):
        await self.run_protocol("success")

    async def test_real_bus_provider_dismissal_stops_admission(self):
        await self.run_protocol("dismissed")

    async def test_real_bus_deadline_dismisses_prompt(self):
        await self.run_protocol("timeout")

    async def test_real_bus_completion_retires_a_prompt_rpc_that_never_replies(self):
        await self.run_protocol("signal-only")

    async def test_real_bus_owner_change_retires_prompt_without_another_unlock(self):
        await self.run_protocol("replacement")

    async def test_real_bus_missing_alias_uses_the_sole_locked_collection(self):
        await self.run_protocol("sole")
