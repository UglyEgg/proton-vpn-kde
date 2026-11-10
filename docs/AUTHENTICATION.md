# Authentication

The protocol below implements the invariants in [SECURITY.md](../SECURITY.md).
Deployment identity checks belong in [Hardening](HARDENING.md); account/process
transitions belong in [Architecture](ARCHITECTURE.md#authentication-and-account-lifecycle).

## Secret transport

The native UI accepts username, password, second-factor/recovery code, and
security-key PIN fields. Submission clears the fields; the client neither
persists nor logs them.

1. Resolve and verify the backend's unique owner before requesting a key.
2. Request an ephemeral X25519 public key scoped to the actual D-Bus sender
   and intended method.
3. Derive an AES-256-GCM key with HKDF-SHA256; encrypt only required fields.
4. Write versioned ciphertext to an anonymous Linux `memfd`, seal writes and
   size changes, rewind, and transfer its descriptor.
5. Validate sender, method, descriptor count, seals, size, schema, allowed fields,
   and types before decryption.
6. Rotate the backend private key before each decryption attempt. A sender,
   operation, or backend generation cannot reuse another operation's key.

Payloads are capped at 16 KiB. Descriptors close on every path; the mutable
input buffer is overwritten. Plaintext does not cross D-Bus. Qt/Python immutable
string copies may remain until allocator reuse; this is not process-memory
protection against root or arbitrary same-user native code.

## Secret Service provider

Before constructing its Core API, the backend enforces Proton's public
`keyring=secret_service` selector through `PROTON_LOADER_OVERRIDES`. Only keyring
selection tokens are replaced; other component overrides retain their meaning.
This policy remains in effect because SSO rechecks selection on later operations.
An unavailable provider fails closed instead of selecting Core's JSON fallback.
Legacy fallback files are neither read for restoration nor migrated or deleted.

Proton SSO stores its session through `org.freedesktop.secrets` using the
separately packaged keyring overlay. Before sending session material, it selects
a same-user provider and pins calls, replies, and prompt signals to that unique
owner. Already-running providers need not have activation files.

An unavailable/replaced owner invalidates the current call and stale connection.
Only the overlay's explicit provider-unavailable/identity-change errors permit
one complete retry against a freshly selected same-user owner. Generic
transport failures and dismissed prompts do not gain that retry. A credential
write followed by an owner change during metadata lookup may repeat the same-key
replacement.

The initial provider is a trusted desktop dependency: portable D-Bus APIs attest
its owner/user, not the executable provenance of a non-dumpable provider.
Collection/alias selection and serialized connection reuse are specified in
the [keyring overlay](../packaging/fedora/keyring-overlay/README.md).
Supported stacks belong in [Compatibility](COMPATIBILITY.md).

During normal startup, a verified locked default/sole collection may receive one
standard `Unlock` request. A returned prompt is handled on the same connection,
with completion subscription installed before `Prompt("")`. Method replies and
completion signals must come from the pinned owner; provider replacement retires
the attempt without prompting its successor. The provider owns the dialog and
password entry. No provider name, executable, or database-specific logic is used.

Prompt completion is not admission proof: lock state and owner are rechecked.
Dismissal ends this activation's admission. Unsupported or failed prompting
returns to passive waiting, without another unlock request. The original admission
deadline bounds the interactive RPC and signal wait; short metadata RPC deadlines
do not limit typing time. Cancellation/timeout cancel and join the owned D-Bus RPC,
request `Dismiss` against the original owner when possible, and close the connection.
Dismiss and disconnect each have a 0.5-second cleanup allowance. No collection is
created by this flow, and no secret is read. An empty/ambiguous provider cannot
supply a locked target for this prompt. Protected cleanup and later lock retries
remain passive.

## Account-facing behavior

- Saved authentication with failed connector initialization remains signed in
  but not ready. The client offers startup retry rather than another login.
- Startup waits for store readiness before any owned Core/session construction,
  rather than accepting a cached logged-in result from another backend. Expired
  waits or repeated refusal require backend retry,
  not sign-out or adapter reset. Bounds and ownership are in
  [Architecture](ARCHITECTURE.md#backend-lifecycle).
- Initial admission permits one standard D-Bus activation request and an empty
  provider's keyring-owned default creation. Subsequent lock retries stay passive.
  Existing collections follow the packaged keyring's default-or-sole rule. A
  missing/stale alias permits fallback only for missing-object errors; access
  failures, ambiguity, and owner changes do not. The provider-owned unlock request
  above is limited to normal admission; observation never creates collections or
  reads secrets.
- Snapshots contain minimum account display metadata, never credentials,
  assertions, certificates, tokens, VPN secrets, or raw API responses.
- Expected failures use fixed public messages. Unexpected provider text and
  tracebacks do not cross D-Bus.
- Owner replacement invalidates pending keys and replies.
- Unconfirmed logout reconciles Core's account/protection state and blocks
  unsafe replacement.
- Other startup failures wait for explicit retry; durable cleanup failure uses
  supervised restart.
- FIDO2 is advertised only when Core supplies the complete cancellable device
  selection/assertion/PIN contract; current limitations are in Compatibility.

## Password managers

Fields support paste and deterministic keyboard navigation. The client neither
queries password-manager databases nor implements a browser-extension protocol.
Desktop Auto-Type depends on the manager/display system; X11-only injection
cannot target a native Wayland window.

Regression coverage includes sender/operation isolation, C++/Python encryption
compatibility, descriptor seals/closure, bounds, tamper/replay rejection,
redaction, authentication factors, expiry, logout, and an encrypted descriptor
D-Bus smoke. Current results belong in the
[assessment](SECURITY-AUDIT-2026-08-30.md).
