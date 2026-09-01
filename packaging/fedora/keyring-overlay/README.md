# Proton keyring Secret Service overlay

This directory builds a separately reviewable Fedora RPM from Proton's exact
`python-proton-keyring-linux` `v0.2.3` source. It does not vendor a modified
copy of Proton's Python package into the Plasma client.

The patch set is provider-neutral:

- prefer the Freedesktop `default` collection alias;
- use the sole advertised collection when that alias is missing or stale;
- create a default collection only when the service advertises none;
- reject an ambiguous multi-collection fallback;
- validate Secret Service availability without reading or creating a secret;
- reuse one serialized D-Bus connection per backend, without caching plaintext;
- close that connection explicitly or through a finalizer; and
- treat an already-absent keyring entry as a normal `KeyError`, without an
  error-level traceback;
- authenticate the same-user provider's root-owned, non-writable native
  executable before sending it secret data; and
- pin every Secret Service call, reply, and prompt signal to that provider's
  unique D-Bus owner, rejecting owner replacement.

GNOME Keyring remains a supported provider, but it is a suggestion rather than
a runtime requirement. System-packaged KeePassXC, KWallet, GNOME Keyring, and
other conforming native Freedesktop Secret Service implementations use the same
code path. User-writable binaries, AppImages, Flatpaks, Snaps, interpreter-hosted
providers, and processes with known code-injection environment variables are
rejected because a provider receives Proton session material.

## Rebuild

On Fedora 44, run:

```bash
packaging/fedora/keyring-overlay/build_overlay_rpm.sh
```

The script downloads the pinned upstream archive, verifies its SHA-256 digest,
verifies every patch against the manifest, and invokes `rpmbuild -ba`. `%check`
runs the focused upstream and overlay tests. Pass a second argument to select a
specific RPM top directory:

```bash
packaging/fedora/keyring-overlay/build_overlay_rpm.sh \
    '' "$PWD/build-keyring-overlay"
```

An already downloaded archive can be supplied as the first argument. Neither
the downloaded archive nor built RPMs belong in Git.

The resulting package provides both the compatibility capability
`proton-keyring-secret-service-provider-agnostic = 1` and the stronger
`proton-keyring-secret-service-authenticated-provider = 1`. The Plasma client
RPM requires the stronger capability until an equivalent implementation is
verified in an upstream package and the dependency can be retired.

## Upstream boundary

The first patch combines the default-alias compatibility and stable-client
identity changes because they modify one small backend implementation and share
the same focused test module. The missing-entry logging and provider-identity
patches remain separate and can be proposed independently. No VPN networking,
session format, or secret storage schema is changed.
