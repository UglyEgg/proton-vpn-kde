# Backend service hardening

The installed backend is an unprivileged, D-Bus-activated systemd user service.
Its sandbox must protect the process without moving VPN networking, session
storage, or privileged split tunneling out of Proton's official components.

## Retained controls

The Fedora service starts the installed backend by its absolute path and uses:

- `NoNewPrivileges=true`, preventing the backend and its children from gaining
  privileges through set-user-ID, set-group-ID, or file capabilities.
- `PrivateTmp=true`, isolating temporary support-report attachments while
  preserving their cleanup lifecycle.
- `ProtectSystem=full`, mounting `/usr`, `/boot`, and `/etc` read-only inside the
  backend service while leaving the user's Proton settings, cache, and selected
  packet-capture directories writable.

Each control passed an independent systemd user-service probe on Fedora 44. The
combined sandbox passed both an official-Core disconnected startup and an
explicit demo-backend lifecycle. Additional probes verified session D-Bus access
to the active Freedesktop Secret Service provider, system D-Bus access to
NetworkManager and Proton's split-tunneling daemon, fixed-scope support-journal
collection in the private temporary directory, and writes to an arbitrary
user-selected capture directory.

## Deliberately excluded controls

The service does not use `ProtectSystem=strict`, `ProtectHome`, or fixed
`ReadWritePaths`. Proton persists account and VPN state below the user's home
directory, and packet capture intentionally accepts any existing writable
directory selected by the user. A static allowlist would either break those
workflows or create a misleadingly incomplete sandbox.

The service also retains host networking, Unix, Internet, netlink, and device
access. The official Core reaches NetworkManager and privileged Proton helpers
over D-Bus, uses network APIs, and may use FIDO2 security keys. Controls such as
`PrivateNetwork`, aggressive `RestrictAddressFamilies`, or `PrivateDevices`
would change or disable supported behavior rather than merely harden it.

The privileged split-tunneling daemon remains Proton's separately packaged
system service. These user-service settings neither grant the KDE backend new
privileges nor modify that daemon's security policy.
