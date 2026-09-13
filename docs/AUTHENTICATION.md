# Authentication security boundary

## Secret transport

The Kirigami process receives text entered into username, password, second-factor,
recovery-code, and security-key PIN fields. It clears those fields immediately
after submission and does not persist or log them.

For each secret operation:

1. The native client resolves the backend name to a unique D-Bus owner and
   verifies its installed executable, systemd unit, UID, loader environment,
   and owner continuity.
2. It requests an ephemeral X25519 public key bound to the actual client sender
   and intended backend method.
3. It derives an AES-256-GCM key with HKDF-SHA256 and encrypts only the required
   fields.
4. It writes the versioned ciphertext to an anonymous Linux `memfd`, seals it
   against writes and size changes, rewinds it, and transfers the descriptor.
5. The backend validates sender, method, descriptor count, seals, payload size,
   schema, field set, and types before decrypting.
6. The backend rotates its private key before each decryption attempt. A key or
   payload cannot be reused by another sender, operation, or backend generation.

Payloads are limited to 16 KiB. The backend closes the descriptor on every path
and overwrites its mutable input buffer. D-Bus monitors see authenticated
ciphertext, not plaintext credentials.

Qt and Python may retain immutable string copies until allocator reuse. The
design does not defend against root, debuggers, or arbitrary same-user native
code with process-memory access.

## Process identity

All packaged entry points use root-owned absolute paths and a shared generated
environment denylist. D-Bus activation crosses dedicated systemd user services
before Qt or Python imports application code. Direct native launches remove
loader/runtime overrides and re-execute `/proc/self/exe` before constructing
`QApplication` when cleanup was required.

These checks resist ordinary and sandboxed session peers. They are current-state
policy, not code-signing identity or durable attestation against arbitrary
same-UID native code. KRunner is therefore an untrusted broker and never handles
authentication material or calls the backend directly.

## Secret Service provider

Proton SSO persists the session through `org.freedesktop.secrets`. The downstream
keyring adapter:

- selects or activates the desktop's provider without sending secrets;
- requires the provider to run as the session user;
- pins calls, replies, and prompt signals to its unique owner;
- fails closed on owner replacement;
- accepts an already-running provider that is not D-Bus activatable; and
- handles absent or stale `default` collection aliases without provider-specific
  KeePassXC logic.

The session bus cannot portably attest the executable behind a non-dumpable
provider. The initially selected same-user provider is a trusted desktop
dependency; unique-owner pinning prevents later replacement but does not prove
package provenance.

The verified overlay and supported provider stack are recorded in
[Compatibility](COMPATIBILITY.md). The client stores only non-secret UI
preferences in KConfig.

## Session and account lifecycle

Saved-session restoration and connector readiness are separate. A restored
session with failed connector initialization remains signed in but not ready;
the UI exposes the startup error and explicit retry. Credentials are not
requested again to mask a networking failure.

Login, second factor, cancellation, FIDO2, logout, expiry, and shutdown share an
authentication-transition owner. Account-scoped work captures the current
session epoch and cannot mutate a replacement account. After Core refreshers
start, replacement credentials require backend process replacement. A private
non-secret handoff and pidfd/start-time check prove outgoing-process death before
new login admission.

Logout disables reconnection, crosses the stable-disconnect boundary, removes
the persisted Proton session, and restores the previous kill-switch preference
if a later step fails. Unconfirmed account or protection state produces explicit
recovery guidance and blocks unsafe admission.

The frontend receives only minimum account display metadata. Snapshots exclude
passwords, factors, recovery codes, assertions, tokens, certificates, private
keys, VPN credentials, human-verification tokens, and raw API responses.

## Password managers

The fields support clipboard paste and deterministic keyboard navigation. The
client does not query a password-manager database or expose a browser-extension
protocol. Desktop Auto-Type depends on the password manager and display system;
X11-only Auto-Type cannot inject into a native Wayland window.

## Failure contract

- Expected failures map to fixed public messages.
- Unexpected provider exception text and tracebacks do not cross D-Bus.
- Owner replacement invalidates pending keys and replies.
- A cancelled or failed logout is reconciled against Core's account state.
- A connector failure after successful session restoration does not erase the
  signed-in fact.
- Ordinary startup failure remains visible without an automatic prompt loop;
  durable cleanup failure uses supervised nonzero restart.

Regression coverage includes owner substitution, sender authorization,
operation isolation, C++/Python encryption compatibility, descriptor seals and
closure, size and field bounds, tamper/replay rejection, exception redaction,
password/TOTP/recovery-code flows, FIDO2 capability gating, session expiry,
transactional logout, and a complete encrypted D-Bus descriptor smoke test.
