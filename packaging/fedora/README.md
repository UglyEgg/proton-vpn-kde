# Fedora packaging

Fedora 44/Plasma 6 is the live-accepted target. The client neither conflicts
with nor obsoletes Proton's GTK client, but concurrent frontends against one
session are unsupported. Exact component floors and validation tiers belong
in [Compatibility](../../docs/COMPATIBILITY.md).

## Package boundary

The spec owns dependencies and installed paths. Native dependencies are Qt 6,
KDE Frameworks 6, Kirigami, and OpenSSL 3; the adapter uses system Python and
packaged Proton modules, not a user virtual environment.

Install the client with the independently packaged
[keyring](keyring-overlay/README.md) and [API-Core](api-core-overlay/README.md)
overlays. Their explicit capabilities prevent incompatible stock replacements.
The client never writes Proton-owned files outside package ownership.

Proton Core's `NetworkManager-openvpn-gnome` dependency is retained; the
frontend does not use its GTK editor. Removing an upstream dependency requires
separate runtime evidence.

## Build

Prepare a fresh RPM top directory from the exact clean release tag:

```bash
version="$(sed -n 's/^Version:[[:space:]]*//p' \
    packaging/fedora/proton-vpn-kde.spec | head -n 1)"
topdir="$PWD/build-release"
packaging/fedora/prepare-rpmbuild-tree.sh \
    "$topdir" "$PWD/packaging/fedora/proton-vpn-kde.spec" "v${version}"
rpmbuild \
    --define "_topdir $topdir" \
    --define "_tmppath $topdir/TMP" \
    -ba "$topdir/SPECS/proton-vpn-kde.spec"
```

Use an exact signed commit for an untagged candidate and retain its identity.
Overlay rebuild commands live in their package guides. Release CI and signing
are specified in [Releasing](../../docs/RELEASING.md).

Without `kf6-kstatusnotifieritem-devel`, the explicit Qt tray fallback is:

```bash
rpmbuild \
    --define "_topdir $topdir" \
    --define "_tmppath $topdir/TMP" \
    -ba --without kstatusnotifier "$topdir/SPECS/proton-vpn-kde.spec"
```

The spec fixes libexec layout and requires Mypy, backend coverage, and CTest in
`%check`. Community reporting/telemetry capabilities are disabled. Skipping
`%check` is not a release build.

Resource timestamps derive from the normalized `.source-commit` epoch, not the
day-resolution RPM changelog. This preserves reproducibility and same-day QML
cache invalidation.

## Installed integration

The payload includes Control Center/agent/backend launchers, matching user units
and D-Bus activation, KRunner/KCM plugins, notifications, translations, icons,
licenses, and documentation. Paths must remain root-owned with standard SELinux
labels; no setuid binary or custom SELinux policy is expected.

Service identity and environment enforcement are specified in
[Hardening](../../docs/HARDENING.md). Inspect ownership in RPM metadata; a
workstation sandbox UID/GID mapping is not evidence of a payload defect.

Runtime notes:

- Restart KRunner after upgrades if it has not discovered the new plugin.
- The KCM stores Plasma preferences; Core owns VPN settings.
- KGlobalAccel actions are unbound until the user assigns them.
- KService owns split-tunnel application discovery.
- An idle disconnected backend may exit while the agent remains resident.

Package policy and installed acceptance are release gates, not inferred from
successful compilation.
