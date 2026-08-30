# Release procedure

Only release from a clean working tree after the version-specific changes are
committed.

## 1. Update release metadata

Update the canonical version in `CMakeLists.txt` and the matching values in:

- `backend/pyproject.toml`;
- `backend/proton_vpn_kde_backend/__init__.py`;
- `packaging/fedora/proton-vpn-kde.spec`;
- `qml/ReleaseNotesPage.qml`;
- `CHANGELOG.md` and packaging documentation.

Update `COMPATIBILITY.md` only with evidence from the installed stack. Review
the current posture and release gates in the security assessment; never carry
an open or ambiguous finding into release notes.

Verify synchronization:

```bash
scripts/check-release-metadata.sh
```

## 2. Verify the source tree

Review `git status --short` and the complete release diff first. The committed
tree must contain no build output, local RPMs, credentials, diagnostics,
machine-specific paths, editor state, or unrelated development debris.

```bash
scripts/check-static-analysis.sh
scripts/check-python-analysis.sh
scripts/check-native-sanitizers.sh
scripts/check-clang-tidy.sh
cmake -S . -B build -G Ninja -DBUILD_TESTING=ON
cmake --build build
ctest --test-dir build --output-on-failure
git diff --check
```

Confirm that the working tree is clean after verification. If a tool changes a
tracked file, review and commit that change before rebuilding.

## 3. Build the Fedora source and binary packages

Build the provider-neutral keyring dependency first. The script fetches and
digest-verifies Proton's pinned upstream source, verifies the patch manifest,
runs the focused test suite in `%check`, and emits both source and binary RPMs:

```bash
packaging/fedora/keyring-overlay/build_overlay_rpm.sh \
    '' "$PWD/build-keyring-overlay"
```

Create a dedicated top directory and release archive, then build with Fedora's
package flags and `%check` enabled:

```bash
mkdir -p build-release/{SOURCES,SPECS,TMP}
git archive --format=tar.gz \
    --prefix=proton-vpn-kde-VERSION/ \
    --output=build-release/SOURCES/proton-vpn-kde-VERSION.tar.gz \
    HEAD
cp packaging/fedora/proton-vpn-kde.spec build-release/SPECS/
rpmbuild \
    --define "_topdir $PWD/build-release" \
    --define "_tmppath $PWD/build-release/TMP" \
    -ba build-release/SPECS/proton-vpn-kde.spec
```

Replace `VERSION` with the verified release version. The resulting build is not
releasable if `%check` is skipped or reports a failure.

The `RPM Package` GitHub Actions workflow repeats both builds from every pushed
commit and pull request. It inspects the main package's identity, dependency
boundary, required payload, ownership, permissions, community reporting feature
gates, digest, and transaction validity; it also verifies the keyring package's
identity, provider-neutral capability, dependency boundary, and payload. Both
sets of binary and source RPMs are retained as CI artifacts for 14 days. These
unsigned CI artifacts are review evidence, not published releases and not a
substitute for the clean-environment live acceptance below.

## 4. Inspect and sign artifacts

- Inspect RPM metadata, dependency generation, payload ownership and modes,
  systemd and D-Bus paths, feature gates, and native hardening.
- Install into a clean Fedora Plasma environment and verify KeePassXC or
  another intended Secret Service provider using the exact keyring adapter
  declared in `COMPATIBILITY.md`; then verify signed-out and signed-in startup,
  server browsing, settings persistence, connect/disconnect, KRunner
  confirmation, resident-agent lifetime, and clean disconnected shutdown.
- Confirm that direct Proton support and crash submission remain disabled in
  community packages.
- Generate SHA-256 checksums for every published source and binary artifact.
- Sign release tags and RPMs with a maintainer-controlled key. Never describe
  an unsigned local package as a signed release, and never imply that a
  community artifact is an official Proton release.
- Publish both source RPMs alongside their binary RPMs to preserve corresponding
  source and the boundary between community code and the Proton keyring rebuild.

## 5. Tag and publish

Create the signed `vVERSION` tag only after the exact commit has completed the
release battery, then verify that the published archive reproduces from that
tag. Release notes must identify the supported stack, known limitations, test
results, checksums, and the project's unofficial status.

The release process must never publish Proton credentials, account data,
private test logs, local signing material, or support bundles.
