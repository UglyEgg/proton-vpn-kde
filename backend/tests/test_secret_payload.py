from __future__ import annotations

import base64
import json
import os
import unittest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from proton_vpn_kde_backend.secret_payload import AAD, KDF_INFO, SecretPayloadReader


class SecretPayloadTests(unittest.TestCase):
    def make_descriptor(self, reader: SecretPayloadReader, payload: object) -> int:
        backend_public_key = x25519.X25519PublicKey.from_public_bytes(
            base64.b64decode(reader.public_key, validate=True)
        )
        ephemeral = x25519.X25519PrivateKey.generate()
        shared_secret = ephemeral.exchange(backend_public_key)
        key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=KDF_INFO,
        ).derive(shared_secret)
        nonce = os.urandom(12)
        plaintext = json.dumps(payload, separators=(",", ":")).encode()
        encrypted = (
            b"\x01"
            + ephemeral.public_key().public_bytes_raw()
            + nonce
            + AESGCM(key).encrypt(nonce, plaintext, AAD)
        )
        descriptor = os.memfd_create("proton-vpn-kde-test", os.MFD_CLOEXEC)
        os.write(descriptor, encrypted)
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor

    def test_reads_and_closes_expected_fields(self):
        reader = SecretPayloadReader()
        original_public_key = reader.public_key
        descriptor = self.make_descriptor(
            reader, {"username": "demo", "password": "not-persisted"}
        )

        payload = reader.read(descriptor, {"username", "password"})

        self.assertEqual("demo", payload["username"])
        self.assertEqual("not-persisted", payload["password"])
        self.assertNotEqual(original_public_key, reader.public_key)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_rejects_extra_fields_without_echoing_values(self):
        reader = SecretPayloadReader()
        descriptor = self.make_descriptor(
            reader, {"code": "123456", "unexpected": "do-not-echo"}
        )

        with self.assertRaises(ValueError) as context:
            reader.read(descriptor, {"code"})

        self.assertNotIn("do-not-echo", str(context.exception))

    def test_rejects_replay_after_rotating_key(self):
        reader = SecretPayloadReader()
        descriptor = self.make_descriptor(reader, {"code": "123456"})
        encrypted = os.pread(descriptor, 16 * 1024, 0)

        self.assertEqual({"code": "123456"}, reader.read(descriptor, {"code"}))

        replay = os.memfd_create("proton-vpn-kde-replay", os.MFD_CLOEXEC)
        os.write(replay, encrypted)
        with self.assertRaisesRegex(ValueError, "could not be decrypted"):
            reader.read(replay, {"code"})

    def test_rejects_tampering_without_echoing_secret(self):
        reader = SecretPayloadReader()
        descriptor = self.make_descriptor(reader, {"pin": "very-secret-pin"})
        encrypted = bytearray(os.pread(descriptor, 16 * 1024, 0))
        os.close(descriptor)
        encrypted[-1] ^= 1
        tampered = os.memfd_create("proton-vpn-kde-tampered", os.MFD_CLOEXEC)
        os.write(tampered, encrypted)

        with self.assertRaises(ValueError) as context:
            reader.read(tampered, {"pin"})

        self.assertNotIn("very-secret-pin", str(context.exception))


if __name__ == "__main__":
    unittest.main()
