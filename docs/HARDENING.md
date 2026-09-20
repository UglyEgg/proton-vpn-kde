# Backend service hardening

## Threat boundary

The protected local adversary is an ordinary or sandboxed process in the same
graphical session with D-Bus access but without arbitrary native-code execution
as the desktop user.

Out of scope:

- root and debuggers;
- arbitrary same-UID native code or process-memory access;
- malicious replacement of user-owned systemd state followed by restoration;
- compromise of Proton Core, NetworkManager, the Secret Service provider, or
  Proton's service.

Linux session D-Bus does not provide code-signing identity. A stronger same-UID
boundary requires a root-controlled service, MAC policy, or equivalent
privileged attestation and would materially change the desktop architecture.

## Deployment controls

The backend, Control Center, and agent are unprivileged D-Bus-activated systemd
user services. Distribution packages and launchers provide:

- root-owned absolute executable paths;
- `NoNewPrivileges=true`;
- isolated Python startup;
- one generated denylist for dynamic-loader, OpenSSL-provider, GIO/GI, Python,
  Qt-plugin, and QML search overrides;
- fixed absolute paths for project-owned `ip` and `journalctl` subprocesses;
- `KillMode=control-group`, `SendSIGKILL=yes`, and an outer 35-second stop
  deadline; and
- a production-fixed backend idle grace, with override only in demo/test mode.

Native direct launches apply the same environment policy before Qt starts and
re-execute `/proc/self/exe` when cleanup changes the environment. D-Bus
activation applies it before the initial executable load.

Repository-channel changes use a fixed Polkit action, fixed package names, and
fixed DNF arguments. No shell or user-selected package name crosses the
privilege boundary. Installed acceptance must cover the interaction between
`pkexec` and the Control Center's `NoNewPrivileges` launch path.

## D-Bus identity and authorization

The well-known name is an address. Native clients resolve it to a unique owner
and verify UID, PID, installed executable, active unit, acceptable unit inputs,
loader environment, and owner continuity. User-writable or mixed-trust service
drop-ins fail closed.

Calls and subscriptions target the verified unique name. Every asynchronous
completion also carries the frontend's backend generation; replacement owners
cannot receive an in-flight call or have stale replies accepted.

At ingress, the backend captures the actual D-Bus sender. Protected methods
require an authorized installed client, then recheck authorization before the
operation body runs. Claims in arguments never substitute for the sender.
Owner loss revokes authorization, leases, and secret keys. Unexpected file
descriptors are closed before ignored or rejected messages leave ingress.

KRunner, global shortcuts, and status-notifier brokers are not authentication
principals. They can request a bounded confirmation surface but cannot invoke
the authorized backend controller directly.

## Lifetime and cancellation

- The backend acquires its bus name without queueing; only the primary owner
  initializes Core.
- Owner-loss events release frontend leases; disconnected idle retirement is
  event-driven.
- Manual and automatic connection work share generation-bound ownership.
  Superseded Core work is shielded, joined, and compensated before ownership
  is released.
- Disconnect crosses Core's public event barrier. Observed `Disconnected`
  alone is not treated as proof that queued provider work has retired.
- Cleanup requests have one admission-to-retirement deadline. Duplicate
  callers cannot extend it.
- Shutdown is singleflight and uses one absolute deadline through controller,
  adapter, capture, background-handler, and thread retirement.
- Unconfirmed retirement exits nonzero so a stale process cannot later mutate
  state beside a replacement.

Account replacement is a process boundary. A private non-secret handoff, pidfd,
and PID start time prove outgoing-process death before new credentials are
accepted. Missing evidence blocks recovery.

## Capture and diagnostic bounds

Direct Proton support and crash-report submission are disabled in community
builds at UI, native, backend, and package-policy boundaries. Optional Core
connection telemetry is also a default-off build capability. On Core 5.7 the
adapter disables the live event queue immediately after settings load and
persists the preference as off on an explicit settings write; a settings read
does not write the user's settings file. Settings and copied community
diagnostics disclose the effective policy. A telemetry-capable build exposes
an explicit preference, with fresh Core profiles projected off until opt-in.

This reporting policy does not block traffic required to authenticate, refresh
account and server state, establish or maintain a VPN connection, or perform an
explicit user-requested service action such as submitting an NPS response.

Community diagnostics are separate from that dormant submission path. Their
formatter accepts only fixed status values, recognized error codes, and
bounded version/OS tokens. No account name, server, IP address, path, log, or
provider exception is read. The user previews the exact text before an
explicit clipboard copy; opening the community tracker sends none of it.
Clipboard history and user-pasted issue text remain outside this boundary.

The dormant support collector has:

- fixed journal sources;
- no shell;
- 20-second process timeout;
- 1 MiB per-source limit; and
- 2 MiB aggregate limit.

Packet capture requires an active supported protocol, an existing writable
absolute directory, and Core's positive reviewed byte cap, currently no more
than 512 MiB. A 15-minute generation-bound watchdog owns Stop. A private atomic
recovery record preserves the original deadline across backend replacement.
Failed or ambiguous Stop retains supervised retry; the adapter never uploads or
rewrites capture data.

## Secret Service and authentication

The keyring overlay requires a same-user Secret Service provider and pins all
traffic to its unique owner. Owner replacement fails closed. The initial
provider remains a trusted desktop dependency because portable session APIs do
not attest its executable provenance.

Authentication fields cross D-Bus only as bounded, authenticated ciphertext in
a sealed descriptor under one-use sender/method-bound keys. Raw provider
exceptions, tracebacks, tokens, and credentials do not enter public state.
See [Authentication](AUTHENTICATION.md).

## Defense-in-depth backlog

`systemd-analyze security --offline=yes --user` scores both services 9.0,
`UNSAFE`, largely because desktop VPN integration requires host networking,
D-Bus, home state, devices, and procfs peer inspection. This is a heuristic, not
a vulnerability result.

Potential additions are `UMask=0077`, an empty `CapabilityBoundingSet`,
`LockPersonality`, `RestrictRealtime`, `RestrictSUIDSGID`,
`SystemCallArchitectures=native`, and selected `ProtectKernel*` directives.
Each requires installed Core, FIDO2, capture, KRunner, KCM, tray, Polkit, and
procfs identity regression testing before adoption.
