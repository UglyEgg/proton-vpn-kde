# Backend service hardening

The installed backend is an unprivileged, D-Bus-activated systemd user service.
Its sandbox must protect the process without moving VPN networking, session
storage, or privileged split tunneling out of Proton's official components.

## Retained controls

The Fedora service starts the installed backend by its absolute path and uses:

- `NoNewPrivileges=true`, preventing the backend and its children from gaining
  privileges through set-user-ID, set-group-ID, or file capabilities.
- an isolated-mode Python launcher plus `UnsetEnvironment` for Python, dynamic
  loader, Qt plugin, and QML import overrides. This makes the packaged unit and
  root-owned launcher a stable identity that native clients can verify before
  sending secrets or control operations.

These controls preserve the backend's ability to authenticate the actual
executable and environment of each D-Bus peer before accepting a mutation.
Support-report temporary files remain mode-restricted and bounded by the
application's explicit cleanup lifecycle.

The 0.11.3 release-battery inspection confirmed that all four ELF files in the
exact locally built `proton-vpn-kde-0.11.3-1.fc44` RPM are position-independent
executables or shared objects with non-executable stacks, GNU RELRO, and
immediate binding. A generic CMake build does not automatically inherit
Fedora's compiler and linker hardening policy.

## Deliberately excluded controls

The service deliberately does not use `PrivateTmp` or `ProtectSystem`. On
Fedora 44 with SELinux, either setting creates a mount namespace from which an
unprivileged process receives `EACCES` for another same-user process's
`/proc/<pid>/exe` and `/proc/<pid>/environ`. Those reads are required to
distinguish the packaged root-owned Plasma clients from an arbitrary same-user
D-Bus process. Keeping a cosmetic mount namespace while disabling executable
authentication would weaken the higher-value security boundary. The backend
already runs without elevated privileges, so the desktop user cannot write the
root-owned system paths that `ProtectSystem=full` would remount read-only.

The service also does not use `ProtectSystem=strict`, `ProtectHome`, or fixed
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

The current installed backend and agent units each receive a 9.0 “UNSAFE”
score from `systemd-analyze security --offline=yes --user`. This heuristic is
not a vulnerability verdict and heavily penalizes capabilities that an
unprivileged desktop integration legitimately retains. It is still useful as a
defense-in-depth backlog. Compatible candidates to evaluate independently are
`UMask=0077`, an empty `CapabilityBoundingSet`, `LockPersonality`,
`RestrictRealtime`, `RestrictSUIDSGID`, `SystemCallArchitectures=native`, and
the `ProtectKernel*` family. Each must pass real Core, FIDO2, packet-capture,
KRunner, KCM, tray, and procfs peer-identity tests before adoption.

## D-Bus process identity

The well-known session-bus name is an address, not an identity. Installed
Control Center and agent clients therefore resolve it to a unique
owner and require that owner to match the active packaged systemd unit, its
immutable root-owned unit inputs, and its root-owned launcher. User-owned,
writable, or mixed-trust drop-ins and unsafe loader or Python-path variables
fail closed. Calls and signals then use the verified unique name so ownership
replacement cannot retarget an in-flight operation.

At the backend ingress boundary, the actual D-Bus sender is captured before
method dispatch. Mutations require a sender whose process is one of the
root-owned native client executables. Claims in method arguments never replace
the sender identity. Authorization and pending secret keys are revoked when
the sender's unique name vanishes. Build-tree tests use an exact-owner pin that
is ignored by installed root-owned executables.

Executable identity is appropriate for isolated project processes such as the
Control Center and agent. It is not sufficient for a shared in-process plugin
host, so `/usr/bin/krunner` is not a trusted backend client. The plugin sends
only validated connection requests to the Control Center activation service,
which requires explicit modal confirmation before its already authenticated
controller acts. The shared plugin host never authenticates to or calls the
backend.
