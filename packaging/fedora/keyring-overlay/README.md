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
  error-level traceback.

GNOME Keyring remains a supported provider, but it is a suggestion rather than
a runtime requirement. KeePassXC and other conforming Freedesktop Secret
Service implementations use the same code path.

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

The resulting package provides
`proton-keyring-secret-service-provider-agnostic = 1`. The Plasma client RPM
requires that capability until an equivalent implementation is verified in an
upstream package and the dependency can be retired.

## Upstream boundary

The first patch combines the default-alias compatibility and stable-client
identity changes because they modify one small backend implementation and share
the same focused test module. The missing-entry logging patch remains separate
and can be proposed independently. No VPN networking, session format, or secret
storage schema is changed.
