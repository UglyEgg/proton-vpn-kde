# Reproducible API-Core overlay

The manifest pins Proton's signed Fedora `5.8.11-1.fc44` beta RPM and rebuilds
it as `5.8.11-1.plasmavpn1.fc44`. The client accepts the stable
`5.8.3-2.plasmavpn1` minimum independently declared in
[`core-compatibility.json`](../core-compatibility.json); a beta build input
does not force stable users onto beta Core.

This is a declared modified Core package, not an official build. It preserves
the compiled vendor networking payload and does not install Proton's GTK client
or combine payloads from other packages. The complete overlay is a Fedora
runtime dependency because of its Protun capability; memory detection alone is
optional and never blocks VPN use.

## Patch scope and upstream handoff

| Patch | Runtime scope | Regression owner |
| --- | --- | --- |
| [0001](patches/0001-share-repeated-server-list-strings.patch) | Per-load sharing of equal immutable server/endpoint strings in fresh and cached lists; binary-status storage and JSON save format unchanged | Payload behavior verifier and [server-cache tests](tests/test_server_cache.py) |
| [0002](patches/0002-avoid-deprecated-fido2-capability-query.patch) | Preserve capability truth table without invoking the deprecated API wrapper | Four capability combinations in the verifier |
| [0003](patches/0003-explicitly-activate-protection-profiles.patch) | Reuse matching profiles and explicitly request/observe activation; preserve protection rules and permanent/unsaved behavior | [Protection activation](tests/test_killswitch_activation.py) |
| [0004](patches/0004-ignore-empty-initial-route-monitor-event.patch) | Ignore route-monitor callbacks without an owned server address | [Route monitor](tests/test_killswitch_route_monitor.py) |

Protection-profile comparison normalizes a copy and ignores only UUID/timestamp.
It does not mutate the request, delete existing profiles, or remove protection
after uncertain activation. Activation work and subscriptions retire on timeout.

The route guard remains necessary on both supported Fedora baselines. Unpatched
5.8.11 passes the original pending-install fixture but fails four subscription/
teardown cases; patched 5.8.3/5.8.11 pass all five. Substituted-I/O fixtures do
not establish live reachability of every interleaving.

Protun transient-key handling is vendor-supplied, not a patch in this set.
NetworkManager may materialize its unsaved profile in root-only volatile
`/run/NetworkManager/system-connections`; it is removed on disconnect and does
not survive reboot. The permanent firewall unit and final-removal cleanup
script remain byte-identical to the vendor.

Patch provenance belongs in `overlay-manifest.json`. Its `upstreamCommit` and
`upstreamPatchSha256` identify source-format contributions, not Proton merges.
The recorded public reference is `v5.8.7`, verified on 2026-10-15; it is not
asserted to be the signed 5.8.11 package's source tag.

Upstream work must remain independent of the GUI/package layout, retain focused
tests and actual authorship, and follow [Contributing](../../../CONTRIBUTING.md).
Submission requires maintainer authorization. Retire a patch only after a
released equivalent passes the same compatibility gates. Patch 0002 does not
supply cancellable multi-key selection or enable FIDO2 sign-in.

## Reconstruction contract

Manifest schema 3 owns:

- vendor NEVRA, complete/header/payload hashes, signing key, and verified source
  references;
- capability origin, patch digests/provenance, and permitted paths;
- before/after hashes for six Python sources and twelve derived bytecode files.

[`rebuild_overlay.py`](rebuild_overlay.py) extracts without installation,
verifies the vendor signature in a temporary unprivileged RPM database, applies
zero-fuzz patches, regenerates only declared bytecode, and compares complete
payload trees. Unexpected paths, content, modes, hardlinks, Python versions,
dependencies, conflicts, obsoletes, or scriptlets fail verification.

The verifier also checks Core's queued-connection contract: newest target wins,
Down during Disconnecting retains it, and the old tunnel's Disconnected promotes
it. That oracle describes consumed upstream behavior, not an additional patch.

## Build and verify

```bash
packaging/fedora/api-core-overlay/build_overlay_rpm.sh \
    /path/to/python3-proton-vpn-api-core-5.8.11-1.fc44.x86_64.rpm
```

The SRPM carries the vendor RPM, manifest, verifier, patches, and offline tests.
`%check` runs build-policy, activation, route, and cache regressions. Release CI
requires byte-identical RPM/SRPM pairs from clean roots; normalized build times
and relative input paths prevent temporary directories entering package metadata.

`NetworkManager-openvpn-gnome` remains an upstream dependency. Telemetry policy
belongs to the consuming client, not these patches. Performance results belong
in [Performance](../../../docs/PERFORMANCE.md); package/live qualification belongs
in the [assessment](../../../docs/SECURITY-AUDIT-2026-08-30.md).

The fixtures never construct a live NetworkManager client and do not replace
installed acceptance or packet-confidentiality testing.
