# Authentication security boundary

## Data flow

The Kirigami process necessarily receives text entered into its username,
password, two-factor, recovery-code, and security-key PIN fields. It clears
secret fields immediately after submission and does not persist or log them.

Ordinary D-Bus string arguments are intentionally not used for secret values.
For each operation, the frontend fetches the backend's current ephemeral X25519
public key, derives an independent AES-256-GCM key with HKDF-SHA256, and
encrypts the minimum required fields. It writes only that versioned ciphertext
to an anonymous Linux `memfd`, applies seals that prevent writing, growing, or
shrinking it, rewinds it, and transfers its Unix file descriptor. The backend
rotates its private key before every decryption attempt, so the key is one-use
and a captured payload cannot be replayed. Even if a session-bus monitor
receives a copy of the descriptor, it contains authenticated ciphertext rather
than credentials.

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

Only Proton's official SSO/session implementation persists the authenticated
session. It uses the Freedesktop Secret Service API and therefore remains
provider-agnostic: KeePassXC, KWallet, GNOME Keyring, or another conforming
implementation can own `org.freedesktop.secrets`. The KDE application stores
only non-secret UI preferences in KConfig.

State snapshots expose connection state and the minimum useful account display
metadata. They must never contain passwords, two-factor values, recovery codes,
FIDO2 assertions, API tokens, certificates, private keys, VPN credentials,
human-verification tokens, or raw API responses.

## Failure handling

Expected authentication failures are converted to fixed messages. Unexpected
exception text is not returned to the UI because third-party exceptions can
embed request details. A failed offline logout keeps the session signed in and
re-enables session services; a confirmed successful logout disconnects first
and asks Proton SSO to remove the persisted session.

Automated coverage includes encrypted descriptor creation, seal verification,
bounded backend reads, descriptor closure, extra-field rejection, tamper and
replay rejection, exception redaction, password login, TOTP/recovery codes,
FIDO2, session expiry, and logout. A cross-language compatibility test encrypts
known test-only fields with the actual C++ frontend implementation and decrypts
them with the actual Python backend implementation. The complete encrypted
D-Bus file-descriptor smoke test also verifies that a tampered payload produces
only the fixed public error name and message, without a traceback.
