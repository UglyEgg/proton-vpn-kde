#!/usr/bin/python3
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
from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType


BUS_NAME = "proton.vpn.app.kde.backend"
OBJECT_PATH = "/proton/vpn/app/kde/backend"
INTERFACE_NAME = "proton.vpn.app.kde.Backend1"
KDF_INFO = b"proton-vpn-kde-auth-v1"
AAD = b"proton.vpn.app.kde.Backend1"


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

    initial = await snapshot(interface)
    assert initial["authState"] == "signed_out"

    login_fd = sealed_payload(
        {"username": "demo-user", "password": "2fa"},
        await interface.call_get_auth_public_key(),
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
        await interface.call_get_auth_public_key(),
    )
    try:
        await interface.call_submit_two_factor(code_fd)
    finally:
        os.close(code_fd)
    authenticated = await snapshot(interface)
    assert authenticated["loggedIn"]
    assert authenticated["accountName"] == "demo-user"
    assert authenticated["planTitle"] == "VPN Plus"

    await interface.call_logout()
    signed_out = await snapshot(interface)
    assert signed_out["authState"] == "signed_out"
    assert not signed_out["loggedIn"]
    print(json.dumps(signed_out, sort_keys=True))
    bus.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
