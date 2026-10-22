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
version and migration plan. Edit the introspection XML under `data/dbus/`, then
run `scripts/generate-dbus-contracts.py`; do not hand-edit the generated native
or Python constants.

No credential, token, private key, raw API response, or exception text that may
contain sensitive data may appear in a D-Bus body, state snapshot, notification,
or log.

## Documentation

Write engineering references for Senior+ readers: contracts, constraints,
commands, evidence, and limits. Omit tutorials, development narration, repeated
assurances, and release-by-release summaries outside the changelog.

| Document | Owns |
| --- | --- |
| README | Product overview, screenshots, evaluation entry points |
| Architecture | Component ownership, contracts, lifecycle, and recovery |
| Authentication | Secret transport and Secret Service trust/operation boundary |
| Hardening | Deployment enforcement, privacy bounds, and safe fault-test isolation |
| Compatibility | Supported versions, dependencies, and validation tiers |
| Feature coverage | User workflows and deliberate constraints |
| Assessment | Current evidence, unresolved findings, and remaining gates |
| Performance | Measurements with build/fixture/method and interpretation limits |
| Roadmap | Open work only |
| Releasing / packaging guides | Release gates / distribution-specific build contracts |
| SECURITY / SUPPORT | Security policy and private disclosure / ordinary issue routing |
| Changelog / Git | Release history / detailed implementation and review history |

Link to the owning reference instead of copying its explanation. Distinguish
public release, working branch, synthetic fixture, and installed acceptance;
never transfer review or test results to an unverified revision. Preserve
required license/provenance notices. Agree on a distinct purpose before adding
another document.

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
Explicitly review any copyright-assignment or sole-creation representations;
confirm that you can truthfully accept the target project's current policy
before submitting code derived from work performed here.

## Licensing

By submitting a contribution, you agree to license it under
`GPL-3.0-or-later` and represent that you have the right to do so. Copyright is
not assigned to this project maintainer.

New project-authored source and build files must carry the repository's SPDX
copyright and license identifiers. Put them in the file's leading comments
when its format permits comments; use a sibling `.license` annotation for
strict JSON and other formats that do not. Do not apply the community
copyright line to Proton-derived patches, imported translation catalogs, or
third-party material.
