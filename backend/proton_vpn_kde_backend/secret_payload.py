# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Decrypt short-lived authentication payloads received through Unix FDs."""

from __future__ import annotations

import base64
import json
import os
from typing import Iterable

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


MAX_SECRET_PAYLOAD = 16 * 1024
PAYLOAD_VERSION = 1
PUBLIC_KEY_SIZE = 32
NONCE_SIZE = 12
TAG_SIZE = 16
KDF_INFO = b"proton-vpn-kde-auth-v1"
AAD = b"quest.entropy.PlasmaVPN.Backend1"


class SecretPayloadReader:
    """Own sender- and operation-bound one-use credential keys."""

    def __init__(self, *, maximum_pending_keys: int = 32):
        self._private_keys: dict[tuple[str, str], x25519.X25519PrivateKey] = {}
        self._maximum_pending_keys = max(1, maximum_pending_keys)

    def issue_public_key(self, sender: str, operation: str) -> str:
        if not sender.startswith(":") or not operation:
            raise ValueError("A valid secret capability is required")
        capability = (sender, operation)
        if capability not in self._private_keys and (
            len(self._private_keys) >= self._maximum_pending_keys
        ):
            raise ValueError("Too many protected operations are pending")
        private_key = x25519.X25519PrivateKey.generate()
        self._private_keys[capability] = private_key
        raw_public_key = private_key.public_key().public_bytes_raw()
        return base64.b64encode(raw_public_key).decode("ascii")

    def revoke_sender(self, sender: str) -> None:
        for capability in tuple(self._private_keys):
            if capability[0] == sender:
                del self._private_keys[capability]

    def read(
        self,
        sender: str,
        operation: str,
        file_descriptor: int,
        required_fields: Iterable[str],
    ) -> dict[str, str]:
        """Read, decrypt, validate, close, and overwrite a credential payload."""
        private_key = self._private_keys.pop((sender, operation), None)
        if private_key is None:
            close_descriptor(file_descriptor)
            raise ValueError("No protected operation is pending")
        encrypted = _read_descriptor(file_descriptor)
        plaintext = bytearray()
        try:
            minimum_size = 1 + PUBLIC_KEY_SIZE + NONCE_SIZE + TAG_SIZE
            if len(encrypted) < minimum_size or encrypted[0] != PAYLOAD_VERSION:
                raise ValueError("The authentication payload has an invalid format")

            public_key_start = 1
            nonce_start = public_key_start + PUBLIC_KEY_SIZE
            ciphertext_start = nonce_start + NONCE_SIZE
            peer_public_key = x25519.X25519PublicKey.from_public_bytes(
                bytes(encrypted[public_key_start:nonce_start])
            )
            shared_secret = private_key.exchange(peer_public_key)
            key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=KDF_INFO,
            ).derive(shared_secret)
            decrypted = AESGCM(key).decrypt(
                bytes(encrypted[nonce_start:ciphertext_start]),
                bytes(encrypted[ciphertext_start:]),
                AAD,
            )
            plaintext.extend(decrypted)
            payload = json.loads(plaintext)
            expected = set(required_fields)
            if not isinstance(payload, dict) or set(payload) != expected:
                raise ValueError("The authentication payload has invalid fields")
            if any(not isinstance(payload[field], str) for field in expected):
                raise ValueError("The authentication payload has invalid values")
            return {field: payload[field] for field in expected}
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("The authentication payload is invalid") from error
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(
                "The authentication payload could not be decrypted"
            ) from error
        finally:
            _overwrite(encrypted)
            _overwrite(plaintext)


def _read_descriptor(file_descriptor: int) -> bytearray:
    if not isinstance(file_descriptor, int) or file_descriptor < 0:
        raise ValueError("The authentication payload is unavailable")

    raw = bytearray()
    try:
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        while len(raw) <= MAX_SECRET_PAYLOAD:
            chunk = os.read(
                file_descriptor,
                min(4096, MAX_SECRET_PAYLOAD + 1 - len(raw)),
            )
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > MAX_SECRET_PAYLOAD:
            raise ValueError("The authentication payload is too large")
        return raw
    finally:
        close_descriptor(file_descriptor)


def close_descriptor(file_descriptor: int) -> None:
    """Close an adopted D-Bus descriptor exactly once, ignoring stale values."""
    if not isinstance(file_descriptor, int) or file_descriptor < 0:
        return
    try:
        os.close(file_descriptor)
    except OSError:
        pass


def _overwrite(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0
