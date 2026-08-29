# Fedora packaging

The RPM is intentionally coexistence-safe. It does not conflict with or
obsolete Proton's GTK client, and it reuses the distribution's installed
`python3-proton-vpn-api-core` networking stack.

Create a release archive from the repository root:

```bash
git archive \
    --format=tar.gz \
    --prefix=proton-vpn-kde-0.10.0/ \
    --output="${HOME}/rpmbuild/SOURCES/proton-vpn-kde-0.10.0.tar.gz" \
    v0.10.0
```

Then build with the direct Plasma status-notifier integration:

```bash
rpmbuild -ba packaging/fedora/proton-vpn-kde.spec
```

For a development machine without `kf6-kstatusnotifieritem-devel`, the Qt
system-tray fallback can be packaged explicitly:

```bash
rpmbuild -ba --without kstatusnotifier packaging/fedora/proton-vpn-kde.spec
```

The fallback remains a Qt/Plasma application and does not introduce GTK or
GNOME dependencies.
