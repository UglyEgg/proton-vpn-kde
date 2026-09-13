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
- require the selected provider to run as the session user before sending it
  secret data;
- support both D-Bus-activated providers and providers that already own the
  service name after desktop autostart; and
- pin every Secret Service call, reply, and prompt signal to that provider's
  unique D-Bus owner, rejecting owner replacement.

GNOME Keyring remains a supported provider, but it is a suggestion rather than
a runtime requirement. KeePassXC, KWallet, GNOME Keyring, and other conforming
Freedesktop Secret Service implementations use the same code path. The desktop-
selected same-user provider is a trusted dependency: D-Bus exposes its unique
owner and Unix user but does not portably attest its executable, especially
when a provider deliberately runs as a non-dumpable process.

An activation response that says the service is not activatable is tolerated
only long enough to resolve the current owner. If no provider is actually
running, owner resolution still fails closed before any secret operation.

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
`proton-keyring-secret-service-owner-pinned = 1`. The Plasma client RPM
requires the stronger capability until an equivalent implementation is
verified in an upstream package and the dependency can be retired.

## Upstream boundary

The first patch combines the default-alias compatibility and stable-connection
changes because they modify one small backend implementation and share the same
focused test module. The missing-entry logging and provider-owner-pinning
patches remain separate and can be proposed independently. No VPN networking,
session format, or secret storage schema is changed.

Existing source files retain Proton's copyright and GPL notices. The new test
module in patch 0001 uses Proton's current 2026 notice and GPL boilerplate.
This prepares the source form for Proton's contribution policy; keeping the
patch locally does not itself assign copyright or constitute Proton review.
Before submission, the human contributor must review every line and determine
that they can truthfully accept Proton's copyright-assignment and sole-creation
terms.
