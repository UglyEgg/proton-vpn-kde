# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Small durable handoff for completion-unknown packet captures."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import stat
import tempfile

from .errors import UserVisibleRuntimeError


PACKET_CAPTURE_RECOVERY_FILENAME = (
    "proton-vpn-kde-packet-capture-recovery-v1.json"
)
PACKET_CAPTURE_RECOVERY_VERSION = 1
PACKET_CAPTURE_RECOVERY_MAX_BYTES = 4096


class PacketCaptureRecoveryJournal:
    """Persist the capture deadline across backend process replacement."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        runtime_value = os.environ.get("XDG_RUNTIME_DIR", "")
        if not runtime_value:
            raise UserVisibleRuntimeError(
                "The desktop runtime directory is unavailable; packet capture "
                "cannot be supervised safely"
            )
        runtime_directory = Path(runtime_value)
        try:
            metadata = runtime_directory.stat()
        except OSError:
            raise UserVisibleRuntimeError(
                "The desktop runtime directory is unavailable; packet capture "
                "cannot be supervised safely"
            ) from None
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise UserVisibleRuntimeError(
                "The desktop runtime directory is not private; packet capture "
                "cannot be supervised safely"
            )
        return runtime_directory / PACKET_CAPTURE_RECOVERY_FILENAME

    def load_deadline(self) -> float | None:
        try:
            descriptor = os.open(
                self._path,
                os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            )
        except FileNotFoundError:
            return None
        except OSError:
            raise UserVisibleRuntimeError(
                "Proton could not read packet-capture recovery state"
            ) from None

        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or metadata.st_size > PACKET_CAPTURE_RECOVERY_MAX_BYTES
            ):
                raise ValueError
            with os.fdopen(descriptor, "r", encoding="utf-8") as recovery_file:
                descriptor = -1
                payload = json.load(recovery_file)
            if (
                not isinstance(payload, dict)
                or set(payload) != {"version", "deadlineBootSeconds"}
                or payload["version"] != PACKET_CAPTURE_RECOVERY_VERSION
                or isinstance(payload["deadlineBootSeconds"], bool)
                or not isinstance(payload["deadlineBootSeconds"], (int, float))
            ):
                raise ValueError
            deadline = float(payload["deadlineBootSeconds"])
            if not math.isfinite(deadline) or deadline <= 0:
                raise ValueError
            return deadline
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
            raise UserVisibleRuntimeError(
                "Proton packet-capture recovery state is invalid"
            ) from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def store_deadline(self, deadline: float) -> None:
        payload = json.dumps(
            {
                "deadlineBootSeconds": float(deadline),
                "version": PACKET_CAPTURE_RECOVERY_VERSION,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self._path.name}.", dir=self._path.parent
            )
            temporary_path = Path(temporary_name)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "wb") as recovery_file:
                    descriptor = -1
                    recovery_file.write(payload)
                    recovery_file.flush()
                    os.fsync(recovery_file.fileno())
                os.replace(temporary_path, self._path)
                temporary_path = None
                self._sync_parent()
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        except OSError:
            raise UserVisibleRuntimeError(
                "Proton could not persist packet-capture recovery state"
            ) from None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def clear(self) -> None:
        try:
            self._path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            raise UserVisibleRuntimeError(
                "Proton could not clear packet-capture recovery state"
            ) from None
        self._sync_parent()

    def _sync_parent(self) -> None:
        try:
            descriptor = os.open(
                self._path.parent,
                os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            raise UserVisibleRuntimeError(
                "Proton could not persist packet-capture recovery state"
            ) from None
