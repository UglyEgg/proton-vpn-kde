# Backend service hardening

[SECURITY.md](../SECURITY.md) owns the attacker model, invariants, exclusions, and
disclosure policy. This document specifies deployed enforcement and validation
constraints; it does not establish a stronger same-UID boundary.

## Deployment controls

Backend, Control Center, and agent use unprivileged, D-Bus-activated systemd
user services with:

- root-owned absolute executable paths and `NoNewPrivileges=true`;
- isolated Python startup and one generated loader/runtime/plugin denylist;
- fixed paths for project subprocesses;
- `KillMode=control-group`, `SendSIGKILL=yes`, and a 35-second outer stop bound;
- production-fixed idle grace; overrides only in demo/tests.

The denylist covers dynamic-loader, OpenSSL-provider, GIO/GI, Python, Qt-plugin,
and QML search overrides. Direct native launches sanitize and re-execute
`/proc/self/exe` before Qt; D-Bus activation sanitizes before initial load.

Mount-namespace confinement is not enabled: host procfs peer inspection must
remain usable under Fedora SELinux. Additional sandbox directives require
installed Core, FIDO2, capture, KRunner, KCM, tray, Polkit, and identity checks.
`systemd-analyze security` is a confinement heuristic, not a vulnerability or
acceptance verdict.

Repository-channel changes use a fixed Polkit action, package allowlist, and
DNF arguments, with no shell. Installed acceptance must verify `pkexec` through
the Control Center's `NoNewPrivileges` launch path.

## D-Bus identity and authorization

| Boundary | Enforcement |
| --- | --- |
| Frontend → backend | Resolve unique owner; verify UID/PID, installed executable, active unit and acceptable inputs, loader environment, and owner continuity |
| Backend ingress | Capture actual sender; authorize packaged client; recheck before protected dispatch |
| Owner replacement | Pin calls/subscriptions; generation-check replies; revoke authority, leases, and secret keys on loss |
| Unexpected descriptors | Close at ingress on ignored/rejected messages |
| Desktop brokers | Explicit presentation/action allowlist and user confirmation; no direct authenticated controller access |

User-writable/mixed-trust unit drop-ins fail closed. Claims in message arguments
never substitute for the real sender. These checks do not provide code signing
or durable attestation against arbitrary native code already running as the
desktop user.

Authentication and provider ownership are specified in
[Authentication](AUTHENTICATION.md); cancellation/retirement contracts in
[Architecture](ARCHITECTURE.md#request-ownership).

## Data and reporting

| Surface | Current boundary |
| --- | --- |
| Community report | Allowlisted state/version/error-code facts; preview then explicit clipboard copy; no account/server/address/path/log/provider text; opening tracker sends no report |
| Proton support submission | Default-off build capability; UI/native/backend/package enforcement; dormant collector uses fixed journal sources, no shell, 20 seconds, 1 MiB/source, 2 MiB total |
| Crash submission | Disabled runtime sender and locked-off preference in community packages |
| Core connection telemetry | Disabled build policy, live queue, and queued events; explicit settings writes persist Off; reads do not rewrite storage |
| Packet capture | Supported Core protocol; positive byte cap ≤512 MiB; existing writable absolute destination; 15-minute watchdog and atomic deadline-preserving recovery record |
| Snapshot addresses | Connection-time observations visible on the session bus; excluded from logs, crash reports, and community diagnostics |

A telemetry-capable build exposes an explicit preference; fresh profiles remain
off until opt-in. Missing/failing telemetry queue controls fail closed. Required
account/server/VPN traffic and explicit NPS actions are unaffected.

Capture Stop remains supervised after failure or ambiguity; the client does not
inspect, upload, rename, or rewrite PCAP output. Clipboard history and user-pasted
reports are outside the client boundary.

## Fault-test isolation

Protected recovery cannot require an ordinary internet route: surviving Core
protection can block it until the replacement tunnel exists. The adapter must
use Core's protected handoff, not remove rules or lower the kill-switch setting.

Run the actual-Core fixture only through:

```bash
scripts/test-core-recovery-isolated.sh /path/to/core/site-packages
```

The launcher requires a hash-checked fixture, unprivileged execution, fresh
user/network namespaces, and a 30-second outer bound. Routing replay refuses
mutations unless both namespace identities differ from the parent and only
loopback exists. It uses dummy links and real policy routing with substituted
provider I/O, not a native plugin or live VPN.

The Fastest fixture additionally checks bounded logical-server changes and
protected handoff ordering in Off/On/Permanent modes. These are behavioral
checks, not end-to-end packet-confidentiality evidence. Results and unqualified
surfaces belong in the [assessment](SECURITY-AUDIT-2026-08-30.md).

Live faults require explicit authorization, an independently supervised recovery
mechanism, and a verified control path unaffected by the fault. Existing
temporary recovery tools are excluded from release packages and are not
qualified for reuse. Before reuse, correct interruption handling and verify the
backup-profile permission postcondition. Namespace tests have no
privileged/host-network fallback.
