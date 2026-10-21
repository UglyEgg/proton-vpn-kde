# Proton keyring Secret Service overlay

Builds a separate Fedora package from pinned Proton
`python-proton-keyring-linux` `v0.2.3` source. Modified Proton code is not
vendored into the community adapter.

## Patch contract

| Patch | Behavior |
| --- | --- |
| [0001](patches/0001-provider-agnostic-secret-service.patch) | Provider-neutral collection selection/validation and one reusable serialized D-Bus connection per backend |
| [0002](patches/0002-avoid-missing-entry-traceback.patch) | Missing entries are ordinary `KeyError`, not error-level tracebacks |
| [0003](patches/0003-pin-secret-service-provider.patch) | Same-user provider selection and unique-owner pinning |
| [0004](patches/0004-recover-secret-service-provider-restart.patch) | Bounded complete-operation retry after explicit provider-unavailable/identity-change detection |

Collection selection prefers `default`; absent/stale aliases use the sole
advertised collection. If none are advertised, create a default; multiple
collections without an unambiguous default fail. Backend validation neither
reads nor creates a secret.

Connections retain no plaintext cache, serialize operations, and close explicitly
or through finalization. Activation failure is tolerated only while resolving
an already-running owner; missing owner still fails before a secret operation.
The call/rebind trust boundary is specified in
[Authentication](../../../docs/AUTHENTICATION.md#secret-service-provider).

GNOME Keyring is suggested, not required. KeePassXC, KWallet, GNOME Keyring, and
other conforming providers use the same path. Verified provider/platform tiers
belong in [Compatibility](../../../docs/COMPATIBILITY.md).

## Rebuild

```bash
packaging/fedora/keyring-overlay/build_overlay_rpm.sh \
    '' "$PWD/build-keyring-overlay"
```

The first argument may name an existing upstream archive. Otherwise the script
downloads it, checks its pinned SHA-256, verifies manifest/patch hashes, and runs
`rpmbuild -ba`. `%check` runs upstream and overlay tests. Archives/build outputs
do not belong in Git.

The package provides:

```text
proton-keyring-secret-service-provider-agnostic = 1
proton-keyring-secret-service-owner-pinned = 1
```

The client requires the stronger owner-pinned capability until an equivalent
released upstream implementation passes its compatibility gates. Debian uses
the same series; build commands are in [Releasing](../../../docs/RELEASING.md).

## Contribution boundary

The patches change no VPN networking, session format, or secret schema.
Alias selection and connection reuse share one implementation/test boundary;
logging, owner pinning, and provider restart remain separate patch units.

Preserve upstream notices and actual patch provenance. Upstream contribution
terms and material AI assistance must be reviewed by the human contributor
before an authorized submission; see [Contributing](../../../CONTRIBUTING.md).
