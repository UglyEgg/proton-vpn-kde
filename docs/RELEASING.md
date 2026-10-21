# Release procedure

Release from a clean immutable commit. Runtime changes invalidate affected
review/acceptance gates. Feature releases require one week of local use;
an abbreviated exact-build soak needs explicit maintainer approval recorded in
the assessment, prior feature-line use, and focused acceptance of corrections.
It does not waive review, packaging, signatures, or UAT.

## 1. Metadata

Synchronize the client version across CMake, Python metadata/runtime, Fedora
spec, Debian changelog, and in-app release notes. Update the dated changelog,
README release status, SECURITY support table, Compatibility, and assessment.
Use final RPM/Debian revisions for public releases; internal milestones are not
published releases.

Before publication, final package metadata may identify a prepared release.
README and Compatibility must say `prepared for release`, and the assessment
must use `Release target:` for that version while retaining the actual public
release separately. The metadata gate rejects mixed prepared/public claims.
Finalize all three documents together before tagging the publication commit.

Overlay versions change only when their payload/package contract changes.
Their manifests and dependency floors must remain aligned with the client.

```bash
scripts/check-release-metadata.sh
scripts/check-documentation-links.py
```

## 2. Review and source gates

Seven isolated reviewers assess the same immutable source: Hostile,
Subtractive, Entropy, Error-Class, HPC/Performance, Hardening/Security, and
Cognitive Load/Code Maintainability. Consolidate after all reports arrive.
Remediation requires focused regressions and corrected-diff re-review.

Run the standard checks in [Contributing](../CONTRIBUTING.md), plus:

```bash
scripts/check-ux-mechanics-freeze.sh
scripts/measure-inspector-retention.sh build
scripts/check-qml-visual-matrix.sh build build/visual-matrix
git diff --check
git status --short
```

The mechanics seal covers the published 0.13 baseline and reviewed 0.14 delta.
Do not refresh hashes to make unreviewed runtime pass. Rebaseline only after
the seven reviews, corrections, regressions, and affected re-review complete.

No build outputs, local packages, secrets, diagnostics, machine-specific paths,
or unrelated changes may enter the source commit.

## 3. Package builds

Build Fedora client/overlays using their owning guides:

- [Client RPM](../packaging/fedora/README.md#build)
- [API-Core RPM/SRPM](../packaging/fedora/api-core-overlay/README.md#build-and-verify)
- [Keyring RPM/SRPM](../packaging/fedora/keyring-overlay/README.md#rebuild)

Build Ubuntu 26.04 in a clean target-distribution environment:

```bash
packaging/debian/keyring-overlay/build-overlay-deb.sh "$PWD/build-deb-keyring"
packaging/debian/api-core-overlay/build-overlay-deb.sh "$PWD/build-deb-api-core"
packaging/debian/build-debs.sh "$PWD/build-deb-client"
```

The API-Core builder verifies the manifest-pinned vendor package. Its
[reconstruction contract](../packaging/debian/api-core-overlay/README.md) is not
a source rebuild of compiled Protun.

Pull requests build and inspect one client/keyring/Core package set without
duplicate feature-branch runs. Tag/manual release workflows repeat Fedora
client and Core builds in clean roots, require identical RPM/SRPM outputs, and
retain artifacts for 14 days. Ubuntu checks all three package sets, transactions,
autopkgtest, and client-removal boundaries. CI artifacts are unsigned evidence.

Use an exact signed commit for candidate builds and the verified signed tag for
publication builds. Never skip package tests.

## 4. Artifact and installed acceptance

Verify metadata/dependencies, ownership/modes, activation paths, feature gates,
ELF hardening, licenses, provenance, exact overlay deltas, and binary/source
checksums. Inspect package metadata rather than interpreting sandbox UID/GID
mapping as installed ownership.

For a live-supported distribution, install all three binary packages and check:

- signed-out, saved-session, and signed-in startup with the intended provider;
- browsing, settings persistence, normal Connect/Disconnect, and recovery;
- tray/KRunner/shortcut confirmation, backend retirement, and agent lifetime;
- opt-in login launch, tray/window startup, and auto-connect with ready/locked
  Secret Service;
- full/split presentation, keyboard navigation, sizing, and monitor changes;
- capture Stop, disconnected shutdown, and disabled reporting;
- previous settings/snapshot contract compatibility and bounded restart guidance
  for unsupported future contracts.

An upgrade must not strand a tunnel because frontend/backend processes span the
transaction. Installation must not enable autostart or overwrite custom entries.

Live fault tests require separate authorization and the independent recovery
boundary in [Hardening](HARDENING.md#fault-test-isolation). Unit/namespace tests
do not grant permission for host fault injection.

A package-validated target can be published without maintainer hardware after
clean build, package-policy, transaction, and autopkgtest gates pass. Keep that
tier explicit until real Plasma reports cover its lifecycle. Record outcomes
and exact versions in the [assessment](SECURITY-AUDIT-2026-08-30.md); maintain the
supported matrix in [Compatibility](COMPATIBILITY.md).

## 5. Sign, publish, and verify

1. Confirm review, package, UAT, soak, and metadata gates.
2. Create/verify signed tag `vVERSION`; rebuild from it and compare unsigned
   outputs with the accepted artifacts.
3. Sign final RPMs, then generate SHA-256 checksums over the final downloads.
4. Sign the checksum manifest; include the public verification key. Sign Debian
   repository metadata if publishing an APT repository.
5. Publish all three RPM/SRPM pairs and all three Debian binary/source sets,
   including debug symbols, `.dsc`, original archives, Debian deltas,
   `.buildinfo`, `.changes`, checksums, and signatures.
6. Download published artifacts and verify signatures/checksums and tag identity.
   Synchronize the approved Git remotes and OpenDesktop listing when publishing
   there; verify active files and remove superseded listings recoverably.

Release notes state support tier, user-visible changes, limits, and unofficial
status. Never publish credentials, private keys, raw diagnostics, or unreviewed
capture data.
