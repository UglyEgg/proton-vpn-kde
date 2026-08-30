#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exercise the sealed-FD authentication contract against the demo backend."""

from __future__ import annotations

import asyncio
import base64
import fcntl
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from dbus_fast import Message
from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, MessageType
from dbus_fast.errors import DBusError


BUS_NAME = "quest.entropy.PlasmaVPN.Backend"
OBJECT_PATH = "/quest/entropy/PlasmaVPN/Backend"
INTERFACE_NAME = "quest.entropy.PlasmaVPN.Backend1"
KDF_INFO = b"proton-vpn-kde-auth-v1"
AAD = b"quest.entropy.PlasmaVPN.Backend1"


def sealed_payload(fields: dict[str, str], backend_public_key: str) -> int:
    peer = x25519.X25519PublicKey.from_public_bytes(
        base64.b64decode(backend_public_key, validate=True)
    )
    ephemeral = x25519.X25519PrivateKey.generate()
    shared_secret = ephemeral.exchange(peer)
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=KDF_INFO,
    ).derive(shared_secret)
    nonce = os.urandom(12)
    plaintext = json.dumps(fields, separators=(",", ":")).encode()
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD)
    payload = b"\x01" + ephemeral.public_key().public_bytes_raw() + nonce + ciphertext
    descriptor = os.memfd_create(
        "proton-vpn-kde-auth-smoke",
        os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
    )
    os.write(descriptor, payload)
    fcntl.fcntl(
        descriptor,
        fcntl.F_ADD_SEALS,
        fcntl.F_SEAL_SEAL
        | fcntl.F_SEAL_SHRINK
        | fcntl.F_SEAL_GROW
        | fcntl.F_SEAL_WRITE,
    )
    os.lseek(descriptor, 0, os.SEEK_SET)
    return descriptor


async def snapshot(interface) -> dict:
    return json.loads(await interface.call_get_snapshot())


async def main() -> None:
    bus = await MessageBus(
        bus_type=BusType.SESSION,
        negotiate_unix_fd=True,
    ).connect()
    introspection = await bus.introspect(BUS_NAME, OBJECT_PATH)
    proxy = bus.get_proxy_object(BUS_NAME, OBJECT_PATH, introspection)
    interface = proxy.get_interface(INTERFACE_NAME)

    unexpected_fd = os.memfd_create(
        "proton-vpn-kde-unexpected-fd",
        os.MFD_CLOEXEC,
    )
    try:
        unexpected_reply = await bus.call(
            Message(
                destination=BUS_NAME,
                path=OBJECT_PATH,
                interface=INTERFACE_NAME,
                member="GetSnapshot",
                unix_fds=[unexpected_fd],
            )
        )
        assert unexpected_reply.message_type is MessageType.ERROR
        assert unexpected_reply.error_name == "org.freedesktop.DBus.Error.InvalidArgs"
        assert unexpected_reply.body == ["Unexpected Unix file descriptors"]
    finally:
        os.close(unexpected_fd)

    initial = await snapshot(interface)
    assert initial["authState"] == "signed_out"
    assert initial["killSwitch"] == 0

    await interface.call_disable_kill_switch_for_login()
    pre_login = await snapshot(interface)
    assert pre_login["killSwitch"] == 0

    rejected_fd = sealed_payload(
        {"username": "demo-user", "password": "tampered"},
        await interface.call_get_auth_public_key("Login"),
    )
    try:
        encrypted = bytearray(os.pread(rejected_fd, 16 * 1024, 0))
        encrypted[-1] ^= 1
        os.close(rejected_fd)
        rejected_fd = os.memfd_create(
            "proton-vpn-kde-auth-rejected",
            os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
        )
        os.write(rejected_fd, encrypted)
        try:
            await interface.call_login(rejected_fd)
        except DBusError as error:
            assert error.type == "quest.entropy.PlasmaVPN.Error.InvalidSecretPayload"
            assert error.text == "Protected authentication data was rejected; try again"
            assert "Traceback" not in str(error)
            assert 'File "' not in str(error)
        else:
            raise AssertionError("tampered authentication data was accepted")
    finally:
        os.close(rejected_fd)

    login_fd = sealed_payload(
        {"username": "demo-user", "password": "2fa"},
        await interface.call_get_auth_public_key("Login"),
    )
    try:
        await interface.call_login(login_fd)
    finally:
        os.close(login_fd)
    challenged = await snapshot(interface)
    assert challenged["authState"] == "two_factor"
    assert not challenged["loggedIn"]

    code_fd = sealed_payload(
        {"code": "123456"},
        await interface.call_get_auth_public_key("SubmitTwoFactor"),
    )
    try:
        await interface.call_submit_two_factor(code_fd)
    finally:
        os.close(code_fd)
    authenticated = await snapshot(interface)
    assert authenticated["loggedIn"]
    assert authenticated["accountName"] == "demo-user"
    assert authenticated["planTitle"] == "VPN Plus"

    try:
        await interface.call_connect_country("NOT-A-COUNTRY")
    except DBusError as error:
        assert error.type == "quest.entropy.PlasmaVPN.Error.OperationFailed"
        assert error.text == "Invalid country code"
        assert "Traceback" not in str(error)
        assert 'File "' not in str(error)
        assert "/workspace/" not in str(error)
    else:
        raise AssertionError("an invalid country code was accepted")

    settings = json.loads(await interface.call_get_settings())
    assert settings["schemaVersion"] == 1
    assert settings["protocol"] == "wireguard"
    assert settings["protocols"][0]["name"] == "WireGuard"

    updated_settings = json.loads(
        await interface.call_update_settings(
            json.dumps(
                {"netShield": 2, "vpnAccelerator": False},
                separators=(",", ":"),
            )
        )
    )
    assert updated_settings["netShield"] == 2
    assert not updated_settings["vpnAccelerator"]

    try:
        await interface.call_update_settings('{"password":"not-a-setting"}')
    except DBusError as error:
        assert error.type == "quest.entropy.PlasmaVPN.Error.InvalidSettings"
        assert "unsupported field" in error.text
        assert "Traceback" not in str(error)
    else:
        raise AssertionError("an unsupported setting was accepted")

    split_tunneling = json.loads(await interface.call_get_split_tunneling())
    assert split_tunneling["schemaVersion"] == 1
    assert split_tunneling["available"]
    assert split_tunneling["paidFeaturesAvailable"]
    assert split_tunneling["mode"] == "exclude"

    updated_split_tunneling = json.loads(
        await interface.call_update_split_tunneling(
            json.dumps(
                {
                    "excludeAppPaths": ["/usr/bin/demo-browser"],
                    "enabled": True,
                },
                separators=(",", ":"),
            )
        )
    )
    assert updated_split_tunneling["enabled"]
    assert updated_split_tunneling["excludeAppPaths"] == ["/usr/bin/demo-browser"]
    assert updated_split_tunneling["excludeIpRangeCount"] == 0

    try:
        await interface.call_update_split_tunneling('{"excludeAppPaths":["/usr/bin"]}')
    except DBusError as error:
        assert error.type == ("quest.entropy.PlasmaVPN.Error.InvalidSplitTunneling")
        assert "specific application" in error.text
        assert "Traceback" not in str(error)
    else:
        raise AssertionError("an unsafe split-tunneling path was accepted")

    custom_dns = json.loads(await interface.call_get_custom_dns())
    assert custom_dns["schemaVersion"] == 1
    assert custom_dns["paidFeaturesAvailable"]
    assert not custom_dns["enabled"]

    updated_custom_dns = json.loads(
        await interface.call_update_custom_dns(
            json.dumps(
                {
                    "servers": [
                        {"address": "1.1.1.1", "enabled": True},
                        {
                            "address": "2606:4700:4700:0:0:0:0:1111",
                            "enabled": False,
                        },
                    ]
                },
                separators=(",", ":"),
            )
        )
    )
    assert updated_custom_dns["servers"][1]["address"] == ("2606:4700:4700::1111")

    try:
        await interface.call_update_custom_dns('{"enabled":true}')
    except DBusError as error:
        assert error.type == "quest.entropy.PlasmaVPN.Error.InvalidCustomDns"
        assert "Disable NetShield" in error.text
        assert "Traceback" not in str(error)
    else:
        raise AssertionError("a custom-DNS conflict was silently accepted")

    await interface.call_update_settings('{"netShield":0}')
    updated_custom_dns = json.loads(
        await interface.call_update_custom_dns('{"enabled":true}')
    )
    assert updated_custom_dns["enabled"]

    report_fd = sealed_payload(
        {
            "username": "demo-user",
            "email": "demo@example.com",
            "description": (
                "The demo support report verifies encrypted transport and "
                "submission without collecting any local diagnostic logs."
            ),
            "includeLogs": "false",
        },
        await interface.call_get_auth_public_key("SubmitSupportReport"),
    )
    try:
        try:
            await interface.call_submit_support_report(report_fd)
        except DBusError as error:
            assert error.type == (
                "quest.entropy.PlasmaVPN.Error.InvalidSupportReport"
            )
            assert error.text == (
                "Direct Proton support submission is disabled in this "
                "unofficial community build"
            )
        else:
            raise AssertionError(
                "an unofficial build accepted a direct Proton support report"
            )
    finally:
        os.close(report_fd)

    await interface.call_logout()
    signed_out = await snapshot(interface)
    assert signed_out["authState"] == "signed_out"
    assert not signed_out["loggedIn"]
    print(json.dumps(signed_out, sort_keys=True))
    bus.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
