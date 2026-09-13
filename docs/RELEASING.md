# Release procedure

Release only from a clean, immutable commit. Runtime changes after review or
acceptance restart the affected gates. Feature releases require one week of
local use on the reviewed runtime before publication.

## 1. Metadata

Synchronize:

- `CMakeLists.txt`;
- `backend/pyproject.toml`;
- `backend/proton_vpn_kde_backend/__init__.py`;
- `packaging/fedora/proton-vpn-kde.spec`;
- all three Debian `debian/changelog` files;
- `qml/ReleaseNotesPage.qml`;
- `CHANGELOG.md`;
- `README.md`, `SECURITY.md`, and `docs/COMPATIBILITY.md`.

A public release requires a dated changelog entry, final RPM and Debian package
revisions, matching security-support table, and current in-app notes. Accepted
internal milestones must not appear as published releases.

```bash
scripts/check-release-metadata.sh
scripts/check-documentation-links.py
```

## 2. Source gate

Seven isolated reviewers assess the same immutable source: Hostile,
Subtractive, Entropy, Error-Class, HPC/Performance, Hardening/Security, and
Cognitive Load/Code Maintainability. Consolidate only after all reports arrive.
Behavioral remediation requires focused regression cases and re-review of the
changed class.

```bash
scripts/check-static-analysis.sh
scripts/check-ux-mechanics-freeze.sh
scripts/check-python-analysis.sh
cmake -S . -B build -G Ninja -DBUILD_TESTING=ON
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
scripts/check-native-sanitizers.sh
scripts/check-clang-tidy.sh
scripts/measure-inspector-retention.sh build
scripts/check-qml-visual-matrix.sh build build/visual-matrix
git diff --check
git status --short
```

The tree must contain no build output, local packages, credentials, diagnostics,
machine-specific paths, editor state, or unrelated changes.

## 3. Packages

Build Fedora overlays first:

```bash
packaging/fedora/keyring-overlay/build_overlay_rpm.sh \
    '' "$PWD/build-keyring-overlay"
packaging/fedora/api-core-overlay/build_overlay_rpm.sh \
    '' "$PWD/build-api-core-overlay"
```

Build the client from the exact commit:

```bash
packaging/fedora/prepare-rpmbuild-tree.sh \
    "$PWD/build-release" \
    "$PWD/packaging/fedora/proton-vpn-kde.spec" \
    HEAD
rpmbuild \
    --define "_topdir $PWD/build-release" \
    --define "_tmppath $PWD/build-release/TMP" \
    -ba build-release/SPECS/proton-vpn-kde.spec
```

Use the verified signed `vVERSION` tag instead of `HEAD` for publication.
`%check` is mandatory.

Build Ubuntu 26.04 packages in that distribution or its clean container. The
client, keyring, and API-Core packages are one release unit:

```bash
packaging/debian/keyring-overlay/build-overlay-deb.sh \
    "$PWD/build-deb-keyring"
packaging/debian/api-core-overlay/build-overlay-deb.sh \
    "$PWD/build-deb-api-core"
packaging/debian/build-debs.sh "$PWD/build-deb-client"
```

The API-Core build downloads and verifies Proton's pinned vendor `.deb` unless
an explicit verified path is supplied. Retain each binary package, the client
debug-symbol package, `.dsc`, original archive, Debian delta, `.buildinfo`, and
`.changes` file.

Pull requests receive one complete client/keyring/Core build and policy
inspection. Feature-branch pushes do not duplicate it. Tag and manual workflows
repeat the Fedora client and API-Core builds in clean roots, require
byte-identical outputs, and retain all three RPM/SRPM pairs for 14 days. The
Ubuntu workflow performs the corresponding three-package build, policy inspection,
install/reinstall, autopkgtest, and removal-boundary checks. CI artifacts are
unsigned evidence, not published packages.

## 4. Artifact and live acceptance

Inspect:

- package metadata, dependencies, payload ownership/modes, systemd/D-Bus paths,
  feature gates, ELF hardening, licenses, and provenance;
- exact changed-path and patch-manifest policy for both overlays;
- the API-Core SRPM's vendor-RPM reconstruction boundary; and
- final binary/source checksums.

Before calling a distribution live-supported, install all three binary packages
in a clean target-distribution Plasma environment. Test:

- signed-out, saved-session, and signed-in startup;
- KeePassXC or another intended Secret Service provider;
- server browsing, settings persistence, Connect/Disconnect, and recovery;
- KRunner confirmation, shortcuts, tray, backend retirement, and agent lifetime;
- opt-in login launch, window/tray startup, and auto-connect with ready and
  locked Secret Service;
- full/split layouts, keyboard navigation, app-owned sizing, and monitor changes;
- packet-capture stop and disconnected shutdown; and
- disabled Proton support/crash submission.

Installation must not enable autostart or overwrite custom autostart entries.
Record exact versions and outcomes in [Compatibility](COMPATIBILITY.md).

A package-validated target may be published without maintainer-owned hardware
when its clean build, package-policy, transaction, and autopkgtest gates pass.
Release notes and compatibility metadata must identify that tier and provide a
field-feedback path. Do not call it live-supported until real Plasma lifecycle
reports cover activation, authentication, connection, recovery, and removal.

## 5. Sign and publish

1. Confirm the review, package, installed-UAT, and soak gates.
2. Create and verify signed tag `vVERSION`.
3. Rebuild from that tag and compare with the verified unsigned outputs.
4. Sign final RPMs and the release checksum manifest with the maintainer key;
   sign Debian `Release` metadata if an APT repository is published.
5. Generate SHA-256 checksums before signing the manifest.
6. Publish all three RPM/SRPM pairs, all three binary/source Debian package
   sets, and checksums.
7. Verify tag signature, release links, downloaded signatures, and checksums.

Release notes identify supported versions, known limitations, validation
results, and unofficial community status. Never publish credentials, account
data, private keys, raw diagnostics, or unreviewed capture data.
