# Architecture

## Goals

1. Make the visible client a native Plasma application: Qt 6, Kirigami,
   `KStatusNotifierItem`, Breeze icons, and Plasma's color scheme.
2. Preserve Proton's existing networking behavior instead of reimplementing
   WireGuard, OpenVPN, Protun, kill switch, or split tunneling in the GUI.
3. Never persist or log credentials, and never expose plaintext credentials
   over D-Bus.
4. Allow the frontend to restart independently from an active VPN connection.
5. Keep the backend boundary desktop-neutral so a CLI or another frontend can
   reuse it later.

## Process boundary

```text
┌─────────────────────────────────────┐
│ proton-vpn-kde                      │
│ C++ / Qt 6 / Kirigami / KF6        │
│                                     │
│ UI · tray · notifications · config │
└─────────────────┬───────────────────┘
                  │ session D-Bus
                  │ proton.vpn.app.kde.Backend1
┌─────────────────▼───────────────────┐
│ proton-vpn-kde-backend              │
│ Python / asyncio / dbus-fast        │
│                                     │
│ auth · state · server selection     │
└─────────────────┬───────────────────┘
                  │ public Python API
┌─────────────────▼───────────────────┐
│ python-proton-vpn-api-core          │
│ official Proton networking stack    │
│                                     │
│ NetworkManager · protocols · KS · ST│
└─────────────────────────────────────┘
```

The split-tunneling system daemon remains unchanged.

## D-Bus contract

- Bus name: `proton.vpn.app.kde.backend`
- Object path: `/proton/vpn/app/kde/backend`
- Interface: `proton.vpn.app.kde.Backend1`

The additive version-one contract currently contains:

- `GetSnapshot() -> JSON string`
- `GetCountries() -> JSON string`
- `GetServers(countryCode) -> JSON string`
- `ConnectFastest()`
- `ConnectCountry(countryCode)`
- `ConnectServer(serverName)`
- `Disconnect()`
- `GetAuthPublicKey() -> base64 X25519 public key`
- `Login(sealedCredentialFd)`
- `SubmitTwoFactor(sealedCodeFd)`
- `CancelLogin()`
- `BeginFido2()`
- `SubmitFido2Pin(sealedPinFd)`
- `CancelFido2()`
- `Logout()`
- `SetReconnectionEnabled(enabled)`
- `SnapshotChanged(JSON string)`

JSON keeps the prototype easy to inspect while `schemaVersion` protects the
boundary. Before a public release, frequently accessed fields can become typed
D-Bus properties without breaking the version-one interface.

No token, password, certificate, private key, or raw API response may appear in
the D-Bus message body or state snapshot. Authentication fields are encrypted
for a one-use backend X25519 public key with HKDF-SHA256 and AES-256-GCM, then
cross the process boundary as ciphertext in a sealed Linux `memfd` sent with
D-Bus Unix file-descriptor passing. The backend rotates its key before every
decryption attempt, reads the bounded payload once, closes the descriptor, and
overwrites its mutable input buffer.

Installed builds use D-Bus activation backed by a systemd user service. The
service is demand-started by the first `GetSnapshot` call and remains separate
from the privileged split-tunneling system daemon.

The official SSO stack reaches Secret Service through a synchronous keyring
API. The backend warms that saved session on a worker thread before creating
the VPN connector. This remains provider-agnostic while preventing a KeePassXC,
KWallet, or other provider unlock prompt from freezing the D-Bus event loop.

## Authentication

The backend calls the official `ProtonVPNAPI` facade for password login,
TOTP/recovery codes, FIDO2 assertions, session data retrieval, and logout.
Successful sessions are persisted by Proton SSO through whichever conforming
Freedesktop Secret Service provider owns `org.freedesktop.secrets`.

The native frontend exposes only non-sensitive account metadata: account name,
human-readable plan title, tier, and maximum connection count. Authentication
errors are mapped to fixed user-facing messages so exception strings cannot
accidentally echo credentials. A session-expired API response disables recovery
and returns the UI to sign-in state.

FIDO2 remains implemented by Proton's official `python3-fido2` integration. The
backend bridges touch, key-selection, and PIN prompts into its authentication
state machine; PINs use the same encrypted descriptor transport. Proton's
current Linux core reports human-verification challenges but does not expose a native
completion callback, so the UI safely directs the user to their Proton account
instead of attempting to handle or export the verification token.

## Reconnection

Unexpected tunnel drops are recovered by a small asyncio subscriber in the
backend. It retains Proton core's current connection and asks the official
connector to reconnect to the same server with the same protocol and backend.
Retries use capped exponential jitter and wait until a network route is
available and the systemd-logind session is unlocked. Authentication, session
limit, 2FA, and certificate-validity errors are not retried; an expired
certificate is handed to Proton's official data refresher.

This replaces only the GTK application's GLib scheduling and monitoring glue.
It does not replace Proton's server construction, NetworkManager backend,
protocol implementation, kill switch, or split-tunneling behavior. Reconnection
is configurable through KConfig and never treats the intentional `Disconnected`
state as a dropped tunnel.

## Plasma integration

The frontend keeps desktop concerns out of the backend. `KNotification` owns
connection popups, KConfig stores user preferences in
`proton-vpn-kderc`, and a `QSortFilterProxyModel` provides zero-copy filtering
for country and server lists. The system tray remains a native
`KStatusNotifierItem` when the KF6 development component is present at build
time.

## Safety rules

- The backend never auto-connects in development mode.
- Mutating operations are serialized.
- The GUI disables connection actions while an operation is active.
- Demo mode is the default path used by tests and visual development.
- The official GTK client may remain installed during development, but is no
  longer required to create the Proton session.
- Direct NetworkManager mutations from the GUI are out of scope.

## Next milestones

1. Incremental server-load updates and sorting controls.
2. Complete Proton settings plus a KCM-compatible configuration surface.
3. KRunner actions and Plasma shortcuts.
4. Split-tunneling application discovery through `KService`, not `.desktop`
   parsing in the GUI.
