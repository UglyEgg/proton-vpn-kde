# Authentication security boundary

## Data flow

The Kirigami process necessarily receives text entered into its username,
password, two-factor, recovery-code, and security-key PIN fields. It clears
secret fields immediately after submission and does not persist or log them.

Ordinary D-Bus string arguments are intentionally not used for secret values.
Before any application call, the installed Control Center and agent resolve the
backend's well-known name to a unique D-Bus owner and check that its current
process matches the packaged, root-owned launcher, active systemd user service,
acceptable unit inputs, and safe loader environment.
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

These process checks defend against ordinary or sandboxed same-session peers;
they are not code-signing identity. Arbitrary native code already executing as
the desktop user can inject into or rewrite same-user processes and can
transiently alter user-owned systemd configuration. That attacker is outside
the authentication boundary unless it must first escape a sandbox or gain
additional authority. The packaged services and launcher still remove a shared
denylist of dynamic-loader, OpenSSL-provider, GIO/GI, Python, Qt-plugin, and QML
search overrides before importing backend or Core code, preventing accidental
or inherited configuration from crossing the narrower supported boundary.

The Control Center's D-Bus activation also enters a dedicated systemd user
service carrying the same denylist before Qt loads. Its desktop entry, Plasma
System Settings module, and resident-agent fallback use configured absolute
paths, so an inherited writable-leading `PATH` cannot substitute a different
client process inside this boundary.

Direct desktop launches and native fallback launches may inherit those same
overrides from a launcher such as KRunner. Both native entry points remove
them before constructing `QApplication` and, only if any were present,
re-execute `/proc/self/exe` with the original arguments and PID. Re-execution
replaces the initial environment visible through `/proc/<pid>/environ`;
`unsetenv` alone does not satisfy the backend's unchanged sender check.
An unsuccessful cleanup or re-execution exits before application startup.
The shared denylist is used without provider-specific exceptions. This is
normalization of inherited configuration, not containment of malicious code
already loaded by the dynamic loader before the initial `main`; arbitrary
same-user native code remains outside the boundary described above. Systemd
service activation still removes overrides before the initial executable load.

The in-process KRunner plug-in is deliberately not a backend client and never
handles authentication material. KRunner, global shortcuts, and D-Bus-exported
tray actions send only bounded connection requests to the Control Center and
require explicit user confirmation there. Synthetic desktop-broker activation
can therefore present a modal but cannot silently mutate VPN state.

The backend accepts at most 16 KiB, validates the exact field set and value
types, closes the received descriptor in every path, and overwrites its mutable
input buffer. Python and Qt may retain immutable string copies in process memory
until their normal allocators reuse them; this design does not claim to defend
against root, a debugger, or arbitrary same-user native code that can read or
modify either process's memory.

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
layout correctly. Before an operation sends session material, the downstream
adapter activates the configured provider without secrets, resolves its unique
D-Bus owner, requires that owner to run as the session user, and pins all later
calls, replies, and prompt signals to that owner. Owner replacement fails
closed. A provider that already owns the name after desktop autostart does not
need to be D-Bus-activatable; the adapter tolerates that activation response
only when current-owner resolution and same-user validation succeed. This is
provider-neutral owner pinning, not KeePassXC-specific logic.

The session bus does not portably attest the executable behind a non-dumpable
provider. KeePassXC on the verified Fedora system denies same-user access to
`/proc/<pid>/exe`, while process names, command lines, and user-owned autostart
units are spoofable. The adapter therefore makes no package-provenance claim:
the desktop-selected same-user Secret Service provider is a trusted dependency.
Pinning prevents a later owner from inheriting the session traffic; it cannot
prove that the initially selected provider is benign.

The verified KeePassXC stack uses the compatible downstream adapter recorded in
[Compatibility](COMPATIBILITY.md); release builds provide it as a separate,
provenance-tracked RPM rather than overwriting the keyring package in place. The
KDE application stores only non-secret UI preferences in KConfig.

State snapshots expose connection state and the minimum useful account display
metadata. They must never contain passwords, two-factor values, recovery codes,
FIDO2 assertions, API tokens, certificates, private keys, VPN credentials,
human-verification tokens, or raw API responses.

## Failure handling

Expected authentication failures are converted to fixed messages. Unexpected
exception text is not returned to the UI because third-party exceptions can
embed request details. Interrupted logout is reconciled against Core's account
state; an exception alone does not prove that the session remains signed in.
Unless logout is confirmed, the adapter attempts to restore a changed
kill-switch preference through Core's settings API. Unconfirmed protection or
account state produces explicit recovery guidance, not a claim of restored
protection or a successful sign-out.

An accepted account transition retains its backend-restart requirement even
when logout fails. Compensation does not restart refreshers or reopen
same-process login. The successful path first stops automatic reconnection,
crosses the stable-disconnect barrier, and asks Proton SSO to remove the
persisted session. Replacement login then requires outgoing-process death and
fresh-process cleanup through the non-secret handoff described in the
[account-transition contract](ARCHITECTURE.md#ownership-consolidation-checkpoint).

Automated coverage includes backend-owner substitution rejection, sender-bound
authorization, per-operation key isolation, encrypted descriptor creation,
seal verification, bounded backend reads, descriptor closure, extra-field
rejection, tamper and replay rejection, exception redaction, password login,
TOTP/recovery codes, the fail-closed FIDO2 capability gate and compatible-Core
FIDO2 flow, session expiry, and transactional logout. A
cross-language compatibility test encrypts known test-only fields with the
actual C++ frontend implementation and decrypts
them with the actual Python backend implementation. The complete encrypted
D-Bus file-descriptor smoke test also verifies that a tampered payload produces
only the fixed public error name and message, without a traceback.
