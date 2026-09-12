# Reproducible API Core overlay

This directory rebuilds the Plasma-compatible API Core package from Proton's
exact signed Fedora `5.6.20-1.fc44` RPM. The vendor RPM is a build input only;
the workflow does not install Proton's GTK client and does not download or
combine payload files from any other package.

The string-sharing optimizations are optional in principle. The current Fedora
client RPM nevertheless requires this package's Protun compatibility capability;
the complete overlay is therefore a runtime dependency of this distribution,
not an optional Fedora installation step.

The first two applied patches share repeated immutable server strings. The
third stops `supports_fido2` from calling API Core's own deprecated capability
property while preserving its availability-and-registered-key truth table.
The fourth marks Protun's ephemeral WireGuard private key as system-owned
instead of `AGENT_OWNED`. Proton already creates this NetworkManager profile
with `save_to_disk=False`; NetworkManager therefore keeps the supplied key in
the unsaved connection instead of asking a desktop secret agent to return it.
On Fedora, NetworkManager may materialize that unsaved profile in its root-only
volatile `/run/NetworkManager/system-connections` directory. The profile is
removed on disconnect and cannot survive a reboot, but this is privileged
runtime storage rather than a process-memory-only claim. The change removes
the desktop-keyring copy and the requirement for a GNOME- or Plasma-specific
NetworkManager secret agent. It does not change the key, protocol, server,
routing, kill switch, split tunneling, account authentication, or native
helper.

The fifth patch explicitly activates NetworkManager protection profiles instead
of relying on device autoconnect. It reuses profiles only when their settings
match the requested protection (apart from UUID/timestamp), observes the actual
active connection, and releases asynchronous work and signal subscriptions on
timeout. It preserves existing protection rules and permanent/unsaved behavior;
it neither deletes pre-existing profiles nor tears down protection after an
uncertain activation. This is an authorized networking-integration correction,
not another memory optimization. Historical revision
`5.6.10-12.plasmavpn1.fc44` also
normalizes the comparison copy to match NetworkManager's stored settings.
Revision `11` introduced explicit activation but could reject its own stored
profile because normalization adds default settings such as the proxy group.
The regression fixture now models that storage boundary. No profile settings
are ignored beyond UUID/timestamp, and the caller's request is not mutated.

`overlay-manifest.json` pins:

- the vendor NEVRA, source RPM name, complete-RPM SHA-256, header SHA-256,
  payload SHA-256, signing-key fingerprint, official key URL, and complete
  signing-key SHA-256;
- all five runtime patch hashes and their provenance;
- every permitted changed installed path;
- the before/after SHA-256 for six Python sources and their twelve derived
  bytecode files.

`rebuild_overlay.py` extracts the pinned RPM without installing it, applies
all patches with zero fuzz, deterministically regenerates only the affected
bytecode, and compares the complete vendor and overlay trees. It imports the
pinned signing key into a temporary unprivileged RPM database solely to verify
the vendor RPM, so a clean builder does not depend on a preconfigured system
keyring. Its behavioral verifier also executes the pinned 5.6.20 connection
state contract that motivates the client's stable-disconnect barrier: newest
queued target wins, Down while Disconnecting retains that target, and the old
tunnel's late Disconnected event promotes it. A future Core that changes this
sequence fails the build and requires an explicit adapter review. A path addition,
removal, mode or hardlink change, unrecorded content change, stale patch, wrong
Python version, or unexpected output hash fails the build. The completed RPM
must also retain Proton's exact dependency, conflict, obsolete, and package
scriptlet sets.

Build and verify with:

```bash
packaging/fedora/api-core-overlay/build_overlay_rpm.sh \
    /path/to/python3-proton-vpn-api-core-5.6.20-1.fc44.x86_64.rpm
```

The resulting SRPM contains the signed vendor RPM, manifest, verifier, and
patches. The binary RPM contains the same payload paths as Proton's RPM, with
only the eighteen manifest-listed file hashes changed. The SRPM also includes
the offline protection-activation regression tests, which run in `%check`.

The spec derives RPM build time from its changelog and refers to source inputs
relative to the RPM build directory. This prevents a caller's temporary top
directory from entering the source-package metadata. Release CI builds the
overlay twice in distinct clean top directories and requires both the RPM and
SRPM to be byte-identical.

The direct `NetworkManager-openvpn-gnome` dependency is deliberately retained
because it belongs to Proton's current Core package contract. Removing it may
be reasonable, but requires separate OpenVPN runtime evidence and is not part
of this overlay.

## Patch scope and upstream handoff

These are downstream changes for the pinned Fedora payload, not evidence of
Proton review, acceptance or endorsement. The manifest's historical
`upstreamCommit` and `upstreamPatchSha256` fields identify the maintainer's
source-format commits and exported patches. They do not mean those commits
were merged by Proton. The first three exports originated from a local
`v5.5.15` checkout; the installed-path adaptations are separately hash-checked
and behavior-tested against the pinned **5.6.20** RPM. The original source
commits include tests, while the five payload patches here change runtime
files only. Those originals are not bundled in this client repository, so the
identifiers alone are not a portable upstream submission.

| Payload patch | Scope and dependency | Existing isolated behavior evidence |
| --- | --- | --- |
| [0001](patches/0001-share-repeated-server-endpoint-strings.patch) | Share equal immutable server/endpoint strings after decoding; preserve model types and values. Source origin: `b007cc956541e5d7c2aa25dbf0ab04b628b90d27`. | Distinct equal strings become shared in fresh logical/physical records. |
| [0002](patches/0002-share-server-strings-during-cache-decoding.patch) | Reuse the sharing policy during cache decoding with a per-load hook factory; builds on 0001. Source origin: `88887e4223aed45b18d2dd7554565278c4dda9c0`. | Cached country and endpoint strings share identity after loading. |
| [0003](patches/0003-avoid-deprecated-fido2-capability-query.patch) | Read current session capability properties without the deprecated API wrapper; independent of string sharing. Source origin: `f39782e411d629694eab174b4b04adc86765d7d8`. | All four capability combinations retain their results, with deprecated-property access forced to fail. |
| [0004](patches/0004-keep-protun-private-key-ephemeral.patch) | Change Protun secret ownership in its existing unsaved profile; a separate interoperability/security decision, not a representation-only optimization. Locally authored payload patch. | Constructed settings retain the supplied secret with the system-owned flag; the mocked NetworkManager add call remains explicitly unsaved. |
| [0005](patches/0005-explicitly-activate-protection-profiles.patch) | Reuse matching protection profiles and explicitly request/observe activation. Originally authored against 5.6.10; its target helper is unchanged in 5.6.20 and the patch is revalidated there. Separate from keyring and memory changes. | Real libnm settings with fake I/O cover inactive/active profiles, mismatches, duplicates, activation failure, autoconnect races, cancellation and late callbacks. The retained-inactive-profile regression fails against the unpatched vendor helper. |

The checks above are in `_verify_behavior` in
[`rebuild_overlay.py`](rebuild_overlay.py). The separate
[`tests/test_rebuild_overlay.py`](tests/test_rebuild_overlay.py) covers the
rebuild mechanism, provenance checks and allowed payload changes, not the
complete upstream unit suite. The queued-connection oracle in the verifier
documents unmodified Core behavior consumed by the community adapter; it is
not another Core fix proposed by these patches. Neither these fixtures nor
aggregate client RSS measurements establish patch-specific performance gains
or live Protun cleanup across every desktop.

Patch 0005's portable tests are in
[`tests/test_killswitch_activation.py`](tests/test_killswitch_activation.py).
They load an explicitly selected helper with `--module` (source tree) or
`--root` (extracted RPM), never construct a real NetworkManager client, and
bound completion waits. They do not establish live protection behavior or
replace installed connect/disconnect and manual-device-disconnect acceptance.

After the Plasma release, prepare source-level contributions separately:

1. Recheck current Proton source and contribution rules. Drop changes already
   implemented upstream; do not mechanically rebase from an old API floor or
   the Fedora installed paths. Keep original author/provenance records and
   reconcile notices on newly introduced test files with their actual
   authorship. Do not imply copyright assignment or Proton authorship merely
   by exporting a patch.
2. Present string sharing as one dependency-ordered series, diagnostic cleanup
   independently, and Protun secret ownership and protection-profile activation
   as separate proposals. Do not
   bundle the Plasma GUI, RPM bytecode, packaging paths or provider-lifecycle
   workarounds into these submissions.
3. Port the focused tests to Proton's current source tree. For sharing, cover
   value/serialization equivalence, non-string and absent fields, fresh and
   cached lists, unchanged plain `CacheHandler` callers, and per-load pool
   lifetime. Preserve the FIDO2 truth-table/deprecation regression. For Protun,
   retain flag/unsaved-profile tests and supply separate connect, reconnect,
   disconnect and suspend-cleanup evidence, including the root-only volatile
   storage caveat and compatibility with Proton's existing desktop clients.
4. Measure the memory patches alone against the same unmodified Core baseline,
   interpreter and sanitized corpus: steady and peak memory, decode time,
   repeated cache loads and retained growth. Report methodology and limits;
   the [client performance record](../../../docs/PERFORMANCE.md) is contextual
   evidence, not a substitute for that comparison.
5. Disclose material AI assistance and verify that the maintainer can accept
   the upstream contribution terms. Propose changes only with separate
   maintainer authorization, then retire an overlay only after a released
   upstream package passes the corresponding compatibility gates.

Patch 0003 does **not** fix cancellable multi-key selection or re-enable FIDO2
in the Plasma client. That is a distinct, unimplemented upstream opportunity
tracked in the [roadmap](../../../docs/ROADMAP.md#upstream-opportunities).
