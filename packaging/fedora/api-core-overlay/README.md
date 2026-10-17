# Reproducible API Core overlay

This directory rebuilds the Plasma-compatible API Core package from Proton's
exact signed Fedora `5.8.11-1.fc44` beta RPM for Plasma VPN 0.14.4.
The client also accepts the existing stable `5.8.3-2.plasmavpn1` overlay.
Installation and live acceptance remain separate gates. The vendor RPM is a
build input only;
the workflow does not install Proton's GTK client and does not download or
combine payload files from any other package.

The string-sharing optimizations are optional in principle. The current Fedora
client RPM nevertheless requires this package's Protun compatibility capability;
the complete overlay is therefore a runtime dependency of this distribution,
not an optional Fedora installation step.

The first patch shares repeated immutable server strings for fresh and cached
lists, including the JSON decoder layered over 5.8.11's new binary cache.
It does not change the binary-status cache or Proton's JSON save format.
The second stops `supports_fido2` from calling API Core's own
deprecated capability property while preserving its
availability-and-registered-key truth table. Proton 5.8.2 incorporated the
previous Protun private-key ownership patch: 5.8.11 supplies the key in its
existing unsaved NetworkManager profile with system-owned secret flags. On
Fedora, NetworkManager may materialize that profile in its root-only volatile
`/run/NetworkManager/system-connections` directory. It is removed on
disconnect and cannot survive a reboot.

The third patch explicitly activates NetworkManager protection profiles instead
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

The fourth patch rejects monitor notifications without an owned server address.
Core 5.8.11 assigns that address before awaiting route installation, correcting
the original pending-route ordering. It still forwards an empty destination in
adversarial subscription and post-teardown fixtures without the guard. Retain
the guard on both 5.8.3 and 5.8.11: all five callback regressions pass with it;
four fail against unpatched 5.8.11. These fake-I/O results do not establish that
all adverse interleavings occur on a live NetworkManager instance.

The consumer's minimum stays `5.8.3-2.plasmavpn1`, independently recorded in
`../core-compatibility.json`. A beta build input must not force stable users
onto beta Core. Existing 5.8.3 packages and Ubuntu's 5.6.10 overlay are unchanged.

`overlay-manifest.json` schema 3 pins:

- the vendor NEVRA, source RPM name, complete-RPM SHA-256, header SHA-256,
  payload SHA-256, signing-key fingerprint, official key URL, and complete
  signing-key SHA-256;
- the signed vendor package version separately from the latest verified public
  source tag and commit. Proton's Fedora `5.8.11` package has no corresponding
  public source tag in the repository as verified on 2026-10-15; `v5.8.7` is
  recorded only as the latest public reference, not as the overlay's source;
- the source of the required Protun capability, now supplied by the pinned
  vendor package rather than a downstream patch;
- all four runtime patch hashes and their provenance;
- every permitted changed installed path;
- the before/after SHA-256 for six Python sources and their twelve derived
  bytecode files.

`rebuild_overlay.py` extracts the pinned RPM without installing it, applies
all patches with zero fuzz, deterministically regenerates only the affected
bytecode, and compares the complete vendor and overlay trees. It imports the
pinned signing key into a temporary unprivileged RPM database solely to verify
the vendor RPM, so a clean builder does not depend on a preconfigured system
keyring. Its behavioral verifier also executes the pinned 5.8.11 connection
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
    /path/to/python3-proton-vpn-api-core-5.8.11-1.fc44.x86_64.rpm
```

The resulting SRPM contains the signed vendor RPM, manifest, verifier, and
patches. The binary RPM contains the same payload paths as Proton's RPM, with
only the eighteen manifest-listed file hashes changed. The SRPM also includes
the offline protection-activation, route-monitor and server-cache regression tests,
which run in `%check`.

The spec derives RPM build time from its changelog and refers to source inputs
relative to the RPM build directory. This prevents a caller's temporary top
directory from entering the source-package metadata. Release CI builds the
overlay twice in distinct clean top directories and requires both the RPM and
SRPM to be byte-identical.

The direct `NetworkManager-openvpn-gnome` dependency is deliberately retained
because it belongs to Proton's current Core package contract. Removing it may
be reasonable, but requires separate OpenVPN runtime evidence and is not part
of this overlay.

Core 5.7 introduced a permanent firewall kill-switch systemd unit and optional
connection telemetry. The overlay preserves the vendor unit and final-removal
cleanup script exactly. Telemetry policy belongs to the consuming client, not
these four compatibility patches: Plasma VPN packages disable the Core event
queue by default and verify that policy in their artifact checks.

## Patch scope and upstream handoff

These are downstream changes for the pinned Fedora payload, not evidence of
Proton review, acceptance or endorsement. The manifest's historical
`upstreamCommit` and `upstreamPatchSha256` fields identify the maintainer's
source-format commits and exported patches. They do not mean those commits
were merged by Proton. The string-sharing contribution is rebased on public
`v5.6.20`, measured against **5.8.3**, and adapted to the pinned **5.8.11**
payload. Existing performance numbers below are historical, not 5.8.11 measurements.
The FIDO2 change retains its original source provenance; protection
activation remains downstream. Source-level tests live with their respective
contributions, while the payload patches here change runtime files only.

A direct 5.7.0-to-5.8.3 vendor-payload comparison found no shared-string pool,
cache decode hook, or equivalent construction-time memory work. The relevant
server-model changes reset load expiration and pair binary status records with
logical servers before updating them. They do not replace PR #27. Proton did
independently incorporate the Protun private-key behavior, so that former
overlay patch is removed rather than carried forward.

| Payload patch | Scope and dependency | Existing isolated behavior evidence |
| --- | --- | --- |
| [0001](patches/0001-share-repeated-server-list-strings.patch) | Share equal immutable server/endpoint strings during fresh and cached loads with a per-load pool. Source origin: `9248915988b290ef83c86af38cad523948c9019d` (PR #27). | Value/serialization preservation, absent/non-string fields, plain-cache compatibility and per-load lifetime are covered upstream; the payload verifier covers both load paths. |
| [0002](patches/0002-avoid-deprecated-fido2-capability-query.patch) | Read current session capability properties without the deprecated API wrapper; independent of string sharing. Source origin: `f39782e411d629694eab174b4b04adc86765d7d8`. | All four capability combinations retain their results, with deprecated-property access forced to fail. |
| [0003](patches/0003-explicitly-activate-protection-profiles.patch) | Reuse matching protection profiles and explicitly request/observe activation. Revalidated against 5.8.11; separate from keyring and memory changes. | Fourteen real-libnm/fake-I/O cases cover inactive/active profiles, mismatches, duplicates, activation failure, autoconnect races, cancellation and late callbacks. |
| [0004](patches/0004-ignore-empty-initial-route-monitor-event.patch) | Ignore notifications while no selected server address is owned. | Five fake-I/O cases cover subscription, pending installation, teardown, valid updates and repeated recovery. Both patched 5.8.3 and 5.8.11 pass. |

Against the same 18,220-server cache on Core 5.8.3, seven isolated runs
measured server-list load PSS at 85,380 KiB without string sharing and a median
62,596 KiB with it (-22,784 KiB, -26.7%). Median load time increased from
360.1 ms to 425.7 ms (+65.6 ms). These are same-host component measurements,
not whole-client RSS claims.

The checks above are in `_verify_behavior` in
[`rebuild_overlay.py`](rebuild_overlay.py). The separate
[`tests/test_rebuild_overlay.py`](tests/test_rebuild_overlay.py) covers the
rebuild mechanism, provenance checks and allowed payload changes, not the
complete upstream unit suite. The queued-connection oracle in the verifier
documents unmodified Core behavior consumed by the community adapter; it is
not another Core fix proposed by these patches. Neither these fixtures nor
aggregate client RSS measurements establish patch-specific performance gains
or live Protun cleanup across every desktop.

Patch 0003's portable tests are in
[`tests/test_killswitch_activation.py`](tests/test_killswitch_activation.py).
They load an explicitly selected helper with `--module` (source tree) or
`--root` (extracted RPM), never construct a real NetworkManager client, and
bound completion waits. They do not establish live protection behavior or
replace installed connect/disconnect and manual-device-disconnect acceptance.
Patch 0004's focused regression is in
[`tests/test_killswitch_route_monitor.py`](tests/test_killswitch_route_monitor.py)
and likewise performs no live NetworkManager operation.
[`tests/test_server_cache.py`](tests/test_server_cache.py) exercises eight
5.8.11 contracts: plain JSON compatibility, decode-time sharing, per-load
pool lifetime, factory lifetime, malformed input, raw binary storage, injected
fetcher caches and non-string/absent server fields.

For remaining source-level contributions:

1. Recheck current Proton source and contribution rules. Drop changes already
   implemented upstream; do not mechanically rebase from an old API floor or
   the Fedora installed paths. Keep original author/provenance records. Proton's
   contribution policy assigns submitted contributions to Proton AG and asks
   the contributor to certify sole creation. Existing Proton files retain
   their upstream notices, and newly introduced upstream files use Proton's
   current copyright and GPL notice. A local patch export does not itself
   perform that assignment or satisfy the contributor certification.
2. Keep string sharing, diagnostic cleanup and protection-profile activation
   as independent proposals. Do not bundle the Plasma GUI, RPM bytecode,
   packaging paths or provider-lifecycle workarounds into these submissions.
3. Port the focused tests to Proton's current source tree. For sharing, cover
   value/serialization equivalence, non-string and absent fields, fresh and
   cached lists, unchanged plain `CacheHandler` callers, and per-load pool
   lifetime. Preserve the FIDO2 truth-table/deprecation regression.
4. Measure the memory patches alone against the same unmodified Core baseline,
   interpreter and sanitized corpus: steady and peak memory, decode time,
   repeated cache loads and retained growth. Report methodology and limits;
   the [client performance record](../../../docs/PERFORMANCE.md) is contextual
   evidence, not a substitute for that comparison.
5. Disclose material AI assistance and verify that the maintainer can accept
   the upstream contribution terms. Propose changes only with separate
   maintainer authorization, then retire an overlay only after a released
   upstream package passes the corresponding compatibility gates.

Patch 0002 does **not** fix cancellable multi-key selection or re-enable FIDO2
in the Plasma client. That is a distinct, unimplemented upstream opportunity
tracked in the [roadmap](../../../docs/ROADMAP.md#upstream-opportunities).
