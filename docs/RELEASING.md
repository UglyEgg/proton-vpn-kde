# Release procedure

Only release from a clean working tree after the version-specific changes are
committed.

Feature releases require at least one week of local use on one immutable
candidate commit after the complete review and package battery passes. Any
runtime change restarts that soak. During the soak, record defects on the
feature branch instead of publishing successive corrective tags; one deliberate
release should represent the complete reviewed feature set.

## 1. Update release metadata

Update the canonical version in `CMakeLists.txt` and the matching values in:

- `backend/pyproject.toml`;
- `backend/proton_vpn_kde_backend/__init__.py`;
- `packaging/fedora/proton-vpn-kde.spec`;
- `qml/ReleaseNotesPage.qml`;
- `CHANGELOG.md` and packaging documentation.

Update [Compatibility](COMPATIBILITY.md) only with evidence from the installed
stack. Review the current posture and release gates in the security assessment;
never carry an open or ambiguous finding into release notes.

A development candidate may retain an `Unreleased` changelog section and a
prerelease RPM suffix. Public-release metadata needs a dated version entry,
the final Fedora release number, and a security-support table in `SECURITY.md`
that matches the published versions. Prepare that metadata before freezing the
release candidate; do not describe a local acceptance build as already released.
The synchronization check below verifies version consistency, not completion
of those publication requirements.

Verify synchronization:

```bash
scripts/check-release-metadata.sh
```

## 2. Verify the source tree

Require seven isolated reviewers on the same immutable candidate: Hostile,
Subtractive, Entropy, Error-Class, HPC/Performance, Hardening/Security, and
Cognitive Load/Code Maintainability. Collect every result before remediation,
consolidate duplicates, and re-review behavioral corrections. The seventh
perspective checks unnecessary abstraction, duplicate ownership, hidden flow,
and the cost of understanding and changing code. Record results in the existing
security assessment; partial coverage and focused fix checks are not a complete
release approval. Preserve earlier review records as explicitly historical.

Review `git status --short` and the complete release diff first. The committed
tree must contain no build output, local RPMs, credentials, diagnostics,
machine-specific paths, editor state, or unrelated development debris.

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

Build the Plasma-compatible API-Core dependency next. Its script fetches and
digest-verifies Proton's exact signed Fedora RPM, applies only the manifest
patch set, rejects every unlisted payload change, runs the behavior checks,
and emits both source and binary RPMs:

```bash
packaging/fedora/api-core-overlay/build_overlay_rpm.sh \
    '' "$PWD/build-api-core-overlay"
```

Create a fresh dedicated top directory with the commit-stamping helper, then
build with Fedora's package flags and `%check` enabled. The helper refuses a
nonempty output directory and normalizes the injected commit marker so the
same source commit produces the same archive. The spec also derives the RPM
header build time from the changelog epoch and uses a fixed non-routable build
host so independent unsigned builds can be compared byte for byte. Embedded Qt
resources instead use the exact normalized source-commit timestamp; distinct
same-day candidates must not reuse older QML disk caches:

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

For a tagged release, replace `HEAD` with the verified signed `vVERSION` tag.
The resulting build is not releasable if `%check` is skipped or reports a
failure.

The `RPM Package` GitHub Actions workflow repeats all three builds from every
pushed commit and pull request. It inspects the main package's identity,
dependency boundary, required payload, ownership, permissions, community
reporting feature gates, digest, and transaction validity; it also verifies
the keyring and API-Core overlays, rebuilds the complete client RPM/SRPM output
set in a second clean top directory under the same normalized RPM build path,
requires byte-identical results, and performs an isolated transaction with the
complete six-artifact set. All binary and source RPMs are retained as CI
artifacts for 14 days. These unsigned CI artifacts are review evidence, not
published releases and not a substitute for the clean-environment live
acceptance below.

## 4. Inspect artifacts and complete acceptance

- Inspect RPM metadata, dependency generation, payload ownership and modes,
  systemd and D-Bus paths, feature gates, and native hardening.
- Install into a clean Fedora Plasma environment and verify KeePassXC or
  another intended Secret Service provider using the exact keyring adapter
  declared in [Compatibility](COMPATIBILITY.md); then verify signed-out and
  signed-in startup, server browsing, settings persistence, connect/disconnect,
  KRunner confirmation, resident-agent lifetime, and clean disconnected shutdown.
- Verify opt-in login launch, window/tray startup, and auto-connect with both
  ready and locked Secret Service. Installation must not enable login launch
  or replace custom autostart entries. Exercise full/split route layouts,
  keyboard navigation, app-owned sizing, and monitor/work-area changes.
- Confirm that direct Proton support and crash submission remain disabled in
  community packages.
- Inspect source content, licenses and provenance for all three package pairs:
  client, keyring overlay, and API Core overlay. The API Core SRPM contains a
  signed vendor binary RPM plus the reconstruction inputs; it is not a complete
  upstream source checkout or an upstream-ready patch submission. Check the
  actual source material rather than treating the `.src.rpm` suffix as proof of
  completeness; see the [overlay packaging boundary](../packaging/fedora/api-core-overlay/README.md).
- Complete and record the one-week exact-candidate soak described above before
  authorizing publication. Package installation alone does not start that gate.

## 5. Tag, sign and publish

Create the signed `vVERSION` tag only after the exact commit has completed the
release battery, then verify that the published archive reproduces from that
tag. Release notes must identify the supported stack, known limitations, test
results, checksums, and the project's unofficial status.

After unsigned reproducibility comparisons and acceptance are complete, sign
the final RPMs with the maintainer-controlled key and verify their signatures.
Generate SHA-256 checksums **after signing**, because signing changes the RPM
bytes. Publish all three binary/source pairs and their final checksums; retain
the exact source commit and build evidence. Never describe an unsigned local
package as a signed release or imply that a community artifact is an official
Proton release.

The release process must never publish Proton credentials, account data,
private test logs, local signing material, or support bundles.
