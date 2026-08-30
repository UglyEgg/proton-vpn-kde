# Contributing

Thank you for helping improve the unofficial Plasma client for Proton VPN.

## Before opening a change

- Search existing issues and pull requests.
- Keep one change focused on one behavior or maintenance concern.
- Discuss large interface, security-boundary, dependency, or networking changes
  before implementation.
- Do not report suspected vulnerabilities in a public issue; follow the
  repository [security policy](SECURITY.md).

Account, billing, Proton service, and unmodified official-package problems are
outside this project's issue tracker. See [Support](SUPPORT.md).

## Architectural boundary

This project deliberately delegates VPN protocols, NetworkManager behavior,
kill switch, split tunneling, session persistence, and server construction to
Proton's official Linux Core. Contributions must not duplicate or bypass those
components without an explicit architecture decision and security review.

The frontend/backend D-Bus contract is versioned. Additive changes must remain
compatible with schema version 1; incompatible changes require a new interface
version and migration plan.

No credential, token, private key, raw API response, or exception text that may
contain sensitive data may appear in a D-Bus body, state snapshot, notification,
or log.

## Development workflow

Build and run the complete test suite:

```bash
cmake -S . -B build -G Ninja -DBUILD_TESTING=ON
cmake --build build
ctest --test-dir build --output-on-failure
scripts/check-static-analysis.sh
scripts/check-python-analysis.sh
# Requires Clang, Clang-Tidy, and compiler-rt:
scripts/check-native-sanitizers.sh
scripts/check-clang-tidy.sh
```

Use the deterministic demo backend for interface development. Tests and demos
must not mutate NetworkManager or a real Proton account.

Changes should include the narrowest useful regression test. Security and
lifecycle controls require both success and failure-path coverage.

## Style

- C++ uses C++20, four-space indentation, Qt ownership conventions, and the
  compiler warning policy defined in CMake. Production source must also pass
  the checked-in Clang-Tidy policy and the address/leak/undefined-behavior
  sanitizer build.
- Python supports 3.11 or newer and must pass Ruff, Mypy, and the measured
  branch-coverage floor recorded in `backend/pyproject.toml`.
- Shell scripts use Bash with `set -euo pipefail` and must pass ShellCheck.
- QML uses Kirigami and semantic Plasma colors, icons, spacing, and typography.
- Documentation should explain decisions and reproducible evidence rather than
  make unverified security or performance claims.

Do not mix mechanical formatting with behavioral changes.

## Commit and pull-request expectations

- Use an imperative, specific commit subject.
- Explain the problem, boundary, solution, tests, and user-visible impact.
- Call out changes to authentication, D-Bus, process lifetime, systemd,
  packaging, or official-Core compatibility.
- Keep generated build trees and local RPM artifacts out of commits.

## AI-assisted contributions

AI-assisted work is permitted, but the human contributor remains responsible
for every submitted line. Disclose material AI assistance in the pull request,
review the complete diff, verify provenance and licensing, and run the required
tests. Generated output must not be presented as independently audited or as
evidence of correctness.

Other upstream projects may impose different contributor or copyright terms.
Confirm that you can truthfully accept an upstream project's policy before
submitting code derived from work performed here.

## Licensing

By submitting a contribution, you agree to license it under
`GPL-3.0-or-later` and represent that you have the right to do so. Copyright is
not assigned to this project maintainer.

New project-authored source and build files must carry the repository's SPDX
copyright and license identifiers. Do not apply the community copyright line
to Proton-derived patches, imported translations, or third-party material.
