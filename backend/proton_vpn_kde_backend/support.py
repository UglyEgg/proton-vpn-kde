"""Consent-gated, byte-bounded diagnostic attachments for support reports."""

from __future__ import annotations

import os
from pathlib import Path
import selectors
import subprocess
from time import monotonic
from typing import Iterable


PER_SOURCE_BYTE_LIMIT = 1024 * 1024
AGGREGATE_BYTE_LIMIT = 2 * 1024 * 1024
COLLECTION_TIMEOUT_SECONDS = 20.0
READ_CHUNK_SIZE = 64 * 1024
TRUNCATION_MARKER = b"\n[Plasma VPN: diagnostic output truncated at the byte limit]\n"

_JOURNAL_SOURCES = (
    (
        "ProtonVPNKDE.log",
        (
            "journalctl",
            "--user",
            "--unit",
            "proton-vpn-kde-backend.service",
            "--no-pager",
            "--utc",
            "--since=-1d",
            "--no-hostname",
        ),
    ),
    (
        "NetworkManager.log",
        (
            "journalctl",
            "--unit",
            "NetworkManager",
            "--no-pager",
            "--utc",
            "--since=-1d",
            "--no-hostname",
        ),
    ),
    (
        "SplitTunneling.log",
        (
            "journalctl",
            "--unit",
            "me.proton.vpn.split_tunneling",
            "--no-pager",
            "--utc",
            "--since=-1d",
            "--no-hostname",
        ),
    ),
)


def collect_support_logs(
    directory: Path,
    *,
    sources: Iterable[tuple[str, tuple[str, ...]]] = _JOURNAL_SOURCES,
    per_source_limit: int = PER_SOURCE_BYTE_LIMIT,
    aggregate_limit: int = AGGREGATE_BYTE_LIMIT,
    timeout_seconds: float = COLLECTION_TIMEOUT_SECONDS,
) -> list[Path]:
    """Collect fixed-scope journals with streaming byte and time ceilings."""
    per_source_limit = max(len(TRUNCATION_MARKER), int(per_source_limit))
    aggregate_limit = max(0, int(aggregate_limit))
    paths: list[Path] = []
    aggregate_bytes = 0
    for filename, command in sources:
        remaining = aggregate_limit - aggregate_bytes
        if remaining <= 0:
            break
        output_path = directory / filename
        byte_limit = min(per_source_limit, remaining)
        kept = _stream_command(
            command,
            output_path,
            byte_limit=byte_limit,
            timeout_seconds=timeout_seconds,
        )
        if kept:
            size = output_path.stat().st_size
            aggregate_bytes += size
            paths.append(output_path)
        else:
            output_path.unlink(missing_ok=True)
    return paths


def _stream_command(
    command: tuple[str, ...],
    output_path: Path,
    *,
    byte_limit: int,
    timeout_seconds: float,
) -> bool:
    process: subprocess.Popen[bytes] | None = None
    selector = selectors.DefaultSelector()
    truncated = False
    timed_out = False
    written = 0
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed argument tuples
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        if process.stdout is None:
            return False
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = monotonic() + max(0.01, timeout_seconds)
        with output_path.open("wb") as output:
            while True:
                remaining_time = deadline - monotonic()
                if remaining_time <= 0:
                    timed_out = True
                    break
                events = selector.select(remaining_time)
                if not events:
                    timed_out = True
                    break
                chunk = os.read(process.stdout.fileno(), READ_CHUNK_SIZE)
                if not chunk:
                    break
                available = byte_limit - written
                if len(chunk) <= available:
                    output.write(chunk)
                    written += len(chunk)
                    continue

                marker = TRUNCATION_MARKER[:byte_limit]
                content_budget = max(0, byte_limit - len(marker))
                if written > content_budget:
                    output.seek(content_budget)
                    output.truncate()
                    written = content_budget
                elif written < content_budget:
                    keep = min(len(chunk), content_budget - written)
                    output.write(chunk[:keep])
                    written += keep
                output.write(marker)
                written += len(marker)
                truncated = True
                break

        if timed_out or truncated:
            _terminate_process(process)
        else:
            process.wait(timeout=1.0)
        return not timed_out and written > 0 and (truncated or process.returncode == 0)
    except (OSError, subprocess.SubprocessError):
        if process is not None:
            _terminate_process(process)
        return False
    finally:
        selector.close()
        if process is not None and process.stdout is not None:
            process.stdout.close()


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=1.0)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=1.0)
        except (OSError, subprocess.TimeoutExpired):
            pass
