#!/usr/bin/python3
"""Verify that the native encryptor and Python decryptor share one protocol."""

from __future__ import annotations

import base64
import os
import subprocess
import sys

from proton_vpn_kde_backend.secret_payload import SecretPayloadReader


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: test-secret-interop.py SECRET_TRANSPORT_VECTOR")

    reader = SecretPayloadReader()
    completed = subprocess.run(
        [sys.argv[1], reader.public_key],
        check=True,
        capture_output=True,
        text=True,
    )
    encrypted = bytearray(base64.b64decode(completed.stdout.strip(), validate=True))
    descriptor = os.memfd_create("proton-vpn-kde-interop", os.MFD_CLOEXEC)
    try:
        os.write(descriptor, encrypted)
        try:
            payload = reader.read(descriptor, {"username", "password"})
        finally:
            # SecretPayloadReader owns and closes every descriptor it receives.
            descriptor = -1
    finally:
        for index in range(len(encrypted)):
            encrypted[index] = 0
        if descriptor >= 0:
            os.close(descriptor)

    assert payload == {
        "username": "interop-user",
        "password": "interop-password",
    }


if __name__ == "__main__":
    main()
