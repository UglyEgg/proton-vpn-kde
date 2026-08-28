"""Consent-gated diagnostic attachments for Proton support reports."""

from __future__ import annotations

from pathlib import Path
import subprocess


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


def collect_support_logs(directory: Path) -> list[Path]:
    """Collect available fixed-scope journals without invoking a shell."""
    paths: list[Path] = []
    for filename, command in _JOURNAL_SOURCES:
        output_path = directory / filename
        try:
            with output_path.open("wb") as output:
                result = subprocess.run(  # noqa: S603 - fixed argument tuples
                    command,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=20,
                )
        except (OSError, subprocess.TimeoutExpired):
            output_path.unlink(missing_ok=True)
            continue
        if result.returncode == 0 and output_path.stat().st_size > 0:
            paths.append(output_path)
        else:
            output_path.unlink(missing_ok=True)
    return paths
