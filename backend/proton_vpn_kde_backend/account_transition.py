# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Non-secret handoff across an account's backend process boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import select
import stat
import tempfile
import uuid

from .capture_recovery import PacketCaptureRecoveryJournal
from .errors import UserVisibleRuntimeError


# An adapter replacement inside the same Python process is not retirement.
PROCESS_GENERATION = uuid.uuid4().hex
ACCOUNT_TRANSITION_FILENAME = "plasma-vpn-account-transition-v1.json"


@dataclass(frozen=True, slots=True)
class AccountTransition:
    process_generation: str
    tunnel_retired: bool
    process_id: int
    process_start_ticks: int


def process_start_ticks(process_id: int) -> int:
    # comm may contain spaces and ')'; the final closing parenthesis ends it.
    fields = Path(f"/proc/{process_id}/stat").read_text().rpartition(") ")[2].split()
    return int(fields[19])


def retired_process_confirmed(record: AccountTransition) -> bool:
    """Check process exit without signaling it or trusting bus-name loss."""
    pidfd_open = getattr(os, "pidfd_open", None)
    if pidfd_open is None:
        raise UserVisibleRuntimeError(
            "Account recovery requires a Python build with Linux pidfd support"
        )
    try:
        descriptor = pidfd_open(record.process_id)
    except ProcessLookupError:
        return True
    except OSError:
        raise UserVisibleRuntimeError("The outgoing backend process could not be verified") from None
    try:
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        if poller.poll(0):
            return True
        try:
            current_start = process_start_ticks(record.process_id)
        except FileNotFoundError:
            return bool(poller.poll(0))
        # PID reuse proves the original process ended; never signal the new one.
        return current_start != record.process_start_ticks
    except (OSError, ValueError, IndexError):
        raise UserVisibleRuntimeError("The outgoing backend process could not be verified") from None
    finally:
        os.close(descriptor)


class AccountTransitionJournal:
    """Keep a bounded request, not credentials, in the private runtime directory.

    The record survives a backend crash/restart, not a desktop logout or reboot.
    Process death eliminates outgoing in-memory refreshers; startup must still
    clear the saved outgoing session before permitting replacement credentials.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or PacketCaptureRecoveryJournal.default_path().with_name(
            ACCOUNT_TRANSITION_FILENAME
        )

    def load(self) -> AccountTransition | None:
        descriptor = -1
        try:
            descriptor = os.open(
                self._path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
            )
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or metadata.st_size > 256
            ):
                raise ValueError
            payload = json.loads(os.read(descriptor, 257))
            if (
                not isinstance(payload, dict)
                or set(payload) != {"version", "process", "tunnelRetired", "pid", "startTicks"}
                or type(payload["version"]) is not int
                or payload["version"] != 1
                or not isinstance(payload["process"], str)
                or len(payload["process"]) != 32
                or any(char not in "0123456789abcdef" for char in payload["process"])
                or type(payload["tunnelRetired"]) is not bool
                or type(payload["pid"]) is not int
                or not 0 < payload["pid"] <= 2**31 - 1
                or type(payload["startTicks"]) is not int
                or payload["startTicks"] <= 0
            ):
                raise ValueError
            return AccountTransition(payload["process"], payload["tunnelRetired"],
                                     payload["pid"], payload["startTicks"])
        except FileNotFoundError:
            return None
        except (OSError, ValueError, UnicodeError, TypeError):
            raise UserVisibleRuntimeError(
                "The account-transition recovery record could not be read safely"
            ) from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def exists(self) -> bool:
        try:
            os.lstat(self._path)
        except FileNotFoundError:
            return False
        except OSError:
            # Keep startup alive until load() can report the uncertainty.
            return True
        return True

    def store(self, *, tunnel_retired: bool) -> None:
        payload = json.dumps({
            "version": 1,
            "process": PROCESS_GENERATION,
            "tunnelRetired": tunnel_retired,
            "pid": os.getpid(),
            "startTicks": process_start_ticks(os.getpid()),
        }).encode("ascii")
        temporary_path: str | None = None
        try:
            descriptor, temporary_path = tempfile.mkstemp(
                prefix=f".{self._path.name}.", dir=self._path.parent
            )
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
            self._sync_parent()
        except OSError:
            raise UserVisibleRuntimeError(
                "The account transition could not be recorded safely"
            ) from None
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass

    def clear(self) -> None:
        try:
            self._path.unlink()
            self._sync_parent()
        except OSError:
            raise UserVisibleRuntimeError(
                "The completed account transition could not be acknowledged"
            ) from None

    def _sync_parent(self) -> None:
        descriptor = os.open(self._path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
