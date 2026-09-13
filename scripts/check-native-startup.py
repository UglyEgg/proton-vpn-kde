#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exercise native startup against the real kernel-visible exec environment."""

from pathlib import Path
import subprocess
import sys
import tempfile


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: check-native-startup.py PROBE CONTRACT")
    probe = str(Path(sys.argv[1]).resolve(strict=True))
    names = [
        line.strip()
        for line in Path(sys.argv[2]).read_text(encoding="ascii").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert names
    cases = 0
    with tempfile.TemporaryDirectory(prefix="plasma-vpn-native-startup-") as directory:
        ordinary = {
            "HOME": directory,
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-test-session",
            "OPENSSL_CONFUSION": "ordinary value",
        }
        arguments = [probe, "--show", "two words", "", "--settings", "Plasma ✓"]

        def check(overrides: dict[str, str], entries: int, failure: int = 0,
                  unset_only: bool = False) -> None:
            nonlocal cases
            argv = [probe, "--unset-only"] if unset_only else arguments
            with subprocess.Popen(
                argv, env=ordinary | overrides, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                    raise
                assert process.returncode == failure, (overrides, stderr)
                expected = f"entry:{process.pid}\n".encode() * entries
            if failure == 0:
                expected += b"\0".join(
                    value.encode() for value in argv + list(ordinary.values())
                ) + b"\0"
            assert stdout == expected, (overrides, stdout, expected)
            cases += 1

        check({}, 1)
        for name in names:
            for value in ("", f"{directory}/absent/{name}"):
                check({name: value}, 2)
        check(dict.fromkeys(names, ""), 2)
        check({"QT_PLUGIN_PATH": "", "PLASMA_VPN_TEST_FAIL_EXEC": "1"}, 1, 1)
        check({"QT_PLUGIN_PATH": "", "PLASMA_VPN_TEST_FAIL_UNSET": "1"}, 1, 1)
        check({"QT_PLUGIN_PATH": ""}, 1, 3, unset_only=True)
    print(f"Native startup: {cases} cases passed (including unset-only negative control)")


if __name__ == "__main__":
    main()
