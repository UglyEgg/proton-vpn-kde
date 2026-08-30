# Authentication security boundary

## Data flow

The Kirigami process necessarily receives text entered into its username,
password, two-factor, recovery-code, and security-key PIN fields. It clears
secret fields immediately after submission and does not persist or log them.

Ordinary D-Bus string arguments are intentionally not used for secret values.
Before any application call, the installed Control Center and agent resolve the
backend's well-known name to a unique D-Bus owner and verify that it is the
packaged, root-owned systemd user service assembled only from immutable
root-owned unit inputs and without unsafe loader variables.
Every later call and signal is pinned to that unique owner. For each secret
operation, the frontend requests an ephemeral X25519 public key bound to both
its actual unique sender and the intended method, derives an independent
AES-256-GCM key with HKDF-SHA256, and encrypts the minimum required fields. It
writes only that versioned ciphertext to an anonymous Linux `memfd`, applies
seals that prevent writing, growing, or
shrinking it, rewinds it, and transfers its Unix file descriptor. The backend
rotates its private key before every decryption attempt, so the key is one-use
and a captured payload cannot be replayed. Even if a session-bus monitor
receives a copy of the descriptor, it contains authenticated ciphertext rather
than credentials. A different client cannot consume the outstanding key, and
owner replacement between key retrieval and submission invalidates the
frontend's service generation instead of retargeting the secret.

The in-process KRunner plug-in is deliberately not a backend client and never
handles authentication material. Its bounded connection requests go to the
Control Center and require explicit user confirmation there.

The backend accepts at most 16 KiB, validates the exact field set and value
types, closes the received descriptor in every path, and overwrites its mutable
input buffer. Python and Qt may retain immutable string copies in process memory
until their normal allocators reuse them; this design does not claim to defend
against root, a debugger, or a same-user process that can read either process's
memory.

## Password managers

The sign-in fields support ordinary clipboard paste and deterministic keyboard
navigation, but the client does not query a password-manager database or expose
a browser-extension protocol. Desktop Auto-Type availability depends on the
password-manager release and display platform; in particular, an X11-only
Auto-Type implementation cannot inject into a native Wayland window. This is
kept outside the authentication contract rather than adding provider-specific
credential lookup or storage.

## Persistence

Only Proton's SSO/session implementation persists the authenticated session.
Its Linux keyring adapter uses the Freedesktop Secret Service API, so KeePassXC,
KWallet, GNOME Keyring, or another implementation can own
`org.freedesktop.secrets` when the adapter handles that provider's collection
layout correctly. The verified KeePassXC stack uses the compatible downstream
adapter recorded in [Compatibility](COMPATIBILITY.md); release builds provide
it as a separate, provenance-tracked RPM rather than overwriting the keyring
package in place. The KDE application stores only non-secret UI
preferences in KConfig.

State snapshots expose connection state and the minimum useful account display
metadata. They must never contain passwords, two-factor values, recovery codes,
FIDO2 assertions, API tokens, certificates, private keys, VPN credentials,
human-verification tokens, or raw API responses.

## Failure handling

Expected authentication failures are converted to fixed messages. Unexpected
exception text is not returned to the UI because third-party exceptions can
embed request details. A failed offline logout keeps the session signed in,
restores the previous kill-switch value through Proton's official settings
save path, and re-enables session services. A rollback failure is surfaced as
a distinct fail-safe error. A confirmed successful logout disconnects first
and asks Proton SSO to remove the persisted session.

Automated coverage includes backend-owner substitution rejection, sender-bound
authorization, per-operation key isolation, encrypted descriptor creation,
seal verification, bounded backend reads, descriptor closure, extra-field
rejection, tamper and replay rejection, exception redaction, password login,
TOTP/recovery codes, FIDO2, session expiry, and transactional logout. A
cross-language compatibility test encrypts known test-only fields with the
actual C++ frontend implementation and decrypts
them with the actual Python backend implementation. The complete encrypted
D-Bus file-descriptor smoke test also verifies that a tampered payload produces
only the fixed public error name and message, without a traceback.
